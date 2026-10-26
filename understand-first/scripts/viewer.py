#!/usr/bin/env python3
import http.client
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 37750
STAGE_COUNT = 6
MAX_BODY_BYTES = 10_000
EVENTS_SHOWN = 100
APPLIED_PREFIX = "- applied in "
WORK_CONCEPT_PREFIX = "  - "
WORK_UNDERSTANDING_LEVELS = ("understood", "partly", "not yet")
LANGUAGE_NAME = re.compile(r"^[A-Za-z0-9 .+#-]{1,40}$")
DIAL_LINE = re.compile(r"^- (?P<language>.+?): rung (?P<rung>\d+), clean streak (?P<streak>\d+)$")
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'"
    ),
}


class Refusal(Exception):
    pass


def data_dir():
    configured = os.environ.get("UNDERSTAND_FIRST_DATA")
    return Path(configured) if configured else Path.home() / ".claude" / "understand-first"


def configured_port():
    return int(os.environ.get("UNDERSTAND_FIRST_PORT", DEFAULT_PORT))


def plugin_version():
    manifest = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    return json.loads(manifest.read_text())["version"]


def viewer_url(port):
    return f"http://127.0.0.1:{port}"


def read_text(path):
    try:
        return path.read_text()
    except FileNotFoundError:
        return ""


def write_atomically(path, text):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text)
    os.replace(temporary, path)


def as_int(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def header_end(lines):
    return next((index for index, line in enumerate(lines) if line.startswith("#")), len(lines))


def parse_header(lines):
    header = {}
    for line in lines[: header_end(lines)]:
        key, separator, value = line.partition(": ")
        if separator:
            header[key] = value.strip()
    return header


def parse_dial(lines):
    dial = []
    in_dial = False
    for line in lines:
        if line.startswith("#"):
            in_dial = line.strip() == "## Code dial"
        elif in_dial and DIAL_LINE.match(line):
            found = DIAL_LINE.match(line)
            dial.append({"language": found["language"], "rung": int(found["rung"]), "streak": int(found["streak"])})
    return dial


def parse_concepts(lines):
    fields = {
        "- status: ": "status",
        "- last verified: ": "verified",
        "- in the learner's words: ": "words",
        "- recall question: ": "recall",
    }
    concepts = []
    for line in lines:
        if line.startswith("### "):
            concepts.append({"name": line[4:].strip(), "status": "", "verified": "", "words": "", "recall": "", "examples": 0, "applied": {}})
        elif concepts and line.startswith("  - "):
            concepts[-1]["examples"] += 1
        elif concepts and line.startswith(APPLIED_PREFIX):
            language, _, note = line[len(APPLIED_PREFIX):].partition(": ")
            if note.strip():
                concepts[-1]["applied"][language.strip()] = note.strip()
        elif concepts:
            for prefix, field in fields.items():
                if line.startswith(prefix):
                    concepts[-1][field] = line[len(prefix):].strip()
    return concepts


def parse_ledger(text):
    lines = text.split("\n")
    return {"header": parse_header(lines), "dial": parse_dial(lines), "concepts": parse_concepts(lines)}


def parse_work(text):
    scalar_fields = {
        "- kind: ": "kind", "- date: ": "date", "- source: ": "source", "- understanding: ": "understanding",
        "- problem: ": "problem", "- solution: ": "solution", "- gaps: ": "gaps",
    }
    entries = []
    for line in text.split("\n"):
        if line.startswith("### "):
            entries.append({"title": line[4:].strip(), "kind": "", "date": "", "source": "", "understanding": "", "problem": "", "solution": "", "gaps": "", "concepts": []})
        elif entries and line.startswith(WORK_CONCEPT_PREFIX):
            name, _, use = line[len(WORK_CONCEPT_PREFIX):].partition(": ")
            if name.strip():
                entries[-1]["concepts"].append({"name": name.strip(), "use": use.strip()})
        elif entries:
            for prefix, field in scalar_fields.items():
                if line.startswith(prefix):
                    entries[-1][field] = line[len(prefix):].strip()
    return [with_known_understanding(entry) for entry in entries]


def with_known_understanding(entry):
    level = entry["understanding"].lower()
    return {**entry, "understanding": level if level in WORK_UNDERSTANDING_LEVELS else "not assessed"}


def parse_events(text):
    events = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def build_state(directory):
    ledger = parse_ledger(read_text(directory / "ledger.md"))
    events = parse_events(read_text(directory / "events.jsonl"))
    header = ledger["header"]
    return {
        "version": plugin_version(),
        "hasLedger": bool(header),
        "stage": as_int(header.get("stage")),
        "stageCount": STAGE_COUNT,
        "stageSince": header.get("stage-since", ""),
        "language": header.get("primary-language", ""),
        "statsMode": header.get("stats-mode", "terminal"),
        "dial": ledger["dial"],
        "concepts": ledger["concepts"],
        "work": parse_work(read_text(directory / "work.md")),
        "eventCount": len(events),
        "events": events[-EVENTS_SHOWN:][::-1],
    }


def set_header_line(text, key, value):
    lines = text.split("\n")
    header = lines[: header_end(lines)]
    existing = next((index for index, line in enumerate(header) if line.startswith(f"{key}: ")), None)
    if existing is not None:
        lines[existing] = f"{key}: {value}"
    else:
        anchor = next((index for index, line in enumerate(header) if line.startswith("primary-language: ")), None)
        lines.insert(0 if anchor is None else anchor + 1, f"{key}: {value}")
    return "\n".join(lines)


def dial_line_index(lines, language):
    in_dial = False
    for index, line in enumerate(lines):
        if line.startswith("#"):
            in_dial = line.strip() == "## Code dial"
        elif in_dial:
            found = DIAL_LINE.match(line)
            if found and found["language"] == language:
                return index
    return None


def last_dial_line_index(lines):
    in_dial = False
    last = None
    for index, line in enumerate(lines):
        if line.startswith("#"):
            in_dial = line.strip() == "## Code dial"
        elif in_dial and DIAL_LINE.match(line):
            last = index
    return last


def with_lowered_rung(text, language):
    lines = text.split("\n")
    index = dial_line_index(lines, language)
    if index is None:
        raise Refusal(f"{language} is not in the code dial.")
    rung = int(DIAL_LINE.match(lines[index])["rung"])
    if rung <= 1:
        raise Refusal(f"{language} is already at rung 1.")
    lines[index] = f"- {language}: rung {rung - 1}, clean streak 0"
    return "\n".join(lines)


def with_language(text, language):
    lines = text.split("\n")
    if dial_line_index(lines, language) is not None:
        return text
    last = last_dial_line_index(lines)
    if last is None:
        raise Refusal("The ledger has no code dial section.")
    lines.insert(last + 1, f"- {language}: rung 1, clean streak 0")
    return "\n".join(lines)


def valid_language(name):
    if not isinstance(name, str) or not LANGUAGE_NAME.match(name.strip()):
        raise Refusal("A language name is 1 to 40 letters, digits, spaces or . + # -")
    return name.strip()


def now_stamp():
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M")


def log_event(directory, event, reason, note, language=""):
    date, time_of_day = now_stamp()
    line = json.dumps({
        "date": date, "time": time_of_day, "ticket": "viewer", "event": event, "concept": "",
        "example": "", "level": "", "result": "", "reason": reason, "note": note, "language": language,
    })
    path = directory / "events.jsonl"
    existing = read_text(path)
    separator = "" if existing == "" or existing.endswith("\n") else "\n"
    write_atomically(path, f"{existing}{separator}{line}\n")


def load_ledger_text(directory):
    text = read_text(directory / "ledger.md")
    if not text:
        raise Refusal("There is no ledger yet. The first session creates it.")
    return text


def change_stage(directory, target):
    text = load_ledger_text(directory)
    current = as_int(parse_header(text.split("\n")).get("stage"))
    updated = set_header_line(set_header_line(text, "stage", str(target)), "stage-since", now_stamp()[0])
    write_atomically(directory / "ledger.md", updated)
    return current


def stage_down(directory, request):
    current = as_int(parse_header(load_ledger_text(directory).split("\n")).get("stage"))
    target = as_int(request.get("to"), current - 1)
    if not 1 <= target < current:
        raise Refusal(f"Stage {current} can only go back to a lower stage, 1 to {current - 1}.")
    change_stage(directory, target)
    log_event(directory, "stage-down", "learner request via the viewer", f"stage {current} to {target}")
    return f"Stage {current} to {target}."


def reset_stage(directory, request):
    if request.get("confirm") is not True:
        raise Refusal("Resetting needs confirmation.")
    current = change_stage(directory, 1)
    log_event(directory, "stage-down", "reset via the viewer", f"stage {current} to 1")
    return "Back to stage 1."


def dial_down(directory, request):
    language = valid_language(request.get("language"))
    updated = with_lowered_rung(load_ledger_text(directory), language)
    write_atomically(directory / "ledger.md", updated)
    log_event(directory, "dial-down", "learner request via the viewer", f"{language} lowered one rung", language)
    return f"{language} lowered one rung."


def add_language(directory, request):
    language = valid_language(request.get("language"))
    write_atomically(directory / "ledger.md", with_language(load_ledger_text(directory), language))
    log_event(directory, "setting-changed", "learner request via the viewer", f"added {language} at rung 1", language)
    return f"{language} added at rung 1."


def set_language(directory, request):
    language = valid_language(request.get("language"))
    text = set_header_line(load_ledger_text(directory), "primary-language", language)
    write_atomically(directory / "ledger.md", with_language(text, language))
    log_event(directory, "setting-changed", "learner request via the viewer", f"primary language {language}", language)
    return f"Primary language is now {language}."


def stats_mode_terminal(directory, request):
    text = set_header_line(load_ledger_text(directory), "stats-mode", "terminal")
    write_atomically(directory / "ledger.md", text)
    log_event(directory, "setting-changed", "learner request via the viewer", "stats-mode terminal")
    return "Hosted dashboard publishing is off."


def stats_mode_dashboard(directory, request):
    text = set_header_line(load_ledger_text(directory), "stats-mode", "dashboard")
    write_atomically(directory / "ledger.md", text)
    log_event(directory, "setting-changed", "learner request, consent given", "stats-mode dashboard")
    return "Hosted dashboard publishing is on."


def skip_gates(directory, request):
    log_event(directory, "gates-skipped", "learner request via the viewer", "skip the gates for the next task")
    return "Noted. Claude will skip the gates for the next task and debrief afterward."


ACTIONS = {
    "stage-down": stage_down,
    "reset-stage": reset_stage,
    "dial-down": dial_down,
    "add-language": add_language,
    "set-language": set_language,
    "stats-mode-terminal": stats_mode_terminal,
    "stats-mode-dashboard": stats_mode_dashboard,
    "skip-gates": skip_gates,
}
COMMAND_LINE_ONLY = {"stats-mode-dashboard"}


def apply_action(directory, request, from_page=False):
    name = request.get("action")
    handler = ACTIONS.get(name)
    if handler is None:
        raise Refusal("Unknown action.")
    if from_page and name in COMMAND_LINE_ONLY:
        raise Refusal("Publishing to a hosted page needs your consent in Claude Code: run /understand-first:menu mode dashboard.")
    return handler(directory, request)


class ViewerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, directory, port):
        super().__init__(("127.0.0.1", port), ViewerHandler)
        self.directory = directory
        self.token = secrets.token_urlsafe(32)
        self.allowed_hosts = {f"127.0.0.1:{self.server_port}", f"localhost:{self.server_port}"}
        self.allowed_origins = {f"http://{host}" for host in self.allowed_hosts}


class ViewerHandler(BaseHTTPRequestHandler):
    server_version = "UnderstandFirstViewer"

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if not self.host_is_allowed():
            return self.send_json(403, {"ok": False, "message": "Host not allowed."})
        routes = {"/": self.send_page, "/api/state": self.send_state, "/api/health": self.send_health}
        route = routes.get(self.path.split("?")[0])
        if route is None:
            return self.send_json(404, {"ok": False, "message": "Not found."})
        route()

    def do_POST(self):
        if self.path != "/api/action":
            return self.send_json(404, {"ok": False, "message": "Not found."})
        refusal = self.refusal_for_untrusted_request()
        if refusal:
            return self.send_json(403, {"ok": False, "message": refusal})
        try:
            request = self.read_json_body()
            message = apply_action(self.server.directory, request, from_page=True)
        except Refusal as refusal_reason:
            return self.send_json(400, {"ok": False, "message": str(refusal_reason)})
        self.send_json(200, {"ok": True, "message": message, "state": build_state(self.server.directory)})

    def host_is_allowed(self):
        return self.headers.get("Host") in self.server.allowed_hosts

    def refusal_for_untrusted_request(self):
        if not self.host_is_allowed():
            return "Host not allowed."
        if not secrets.compare_digest(self.headers.get("X-Token", ""), self.server.token):
            return "Missing or wrong token."
        origin = self.headers.get("Origin")
        if origin is not None and origin not in self.server.allowed_origins:
            return "Origin not allowed."
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin"):
            return "Cross-site request refused."
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return "Send JSON."
        return ""

    def read_json_body(self):
        length = as_int(self.headers.get("Content-Length"))
        if not 0 < length <= MAX_BODY_BYTES:
            raise Refusal("The request body is missing or too large.")
        try:
            request = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            raise Refusal("The request is not valid JSON.")
        if not isinstance(request, dict):
            raise Refusal("The request must be a JSON object.")
        return request

    def send_page(self):
        template = (PLUGIN_ROOT / "viewer" / "index.html").read_text()
        self.send_bytes(200, "text/html; charset=utf-8", template.replace("__TOKEN__", self.server.token).encode())

    def send_state(self):
        self.send_json(200, build_state(self.server.directory))

    def send_health(self):
        self.send_json(200, {"app": "understand-first", "version": plugin_version()})

    def send_json(self, status, payload):
        self.send_bytes(status, "application/json", json.dumps(payload).encode())

    def send_bytes(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def pidfile_path():
    return data_dir() / "viewer.pid"


def read_pidfile():
    try:
        return json.loads(pidfile_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def process_is_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def is_healthy(port):
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
        connection.request("GET", "/api/health", headers={"Host": f"127.0.0.1:{port}"})
        answer = json.loads(connection.getresponse().read())
    except (OSError, json.JSONDecodeError, http.client.HTTPException):
        return False
    return answer.get("app") == "understand-first"


def wait_until_healthy(port, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if is_healthy(port):
            return True
        time.sleep(0.1)
    return False


def start_detached():
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / "viewer.log", "ab") as log:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "serve"],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, close_fds=True,
        )


def stop_running_viewer():
    running = read_pidfile()
    if running and process_is_alive(running["pid"]):
        os.kill(running["pid"], signal.SIGTERM)
    pidfile_path().unlink(missing_ok=True)
    return running is not None


def command_ensure(arguments):
    running = read_pidfile()
    is_current = running and process_is_alive(running["pid"]) and running["version"] == plugin_version()
    if is_current and is_healthy(running["port"]):
        print(viewer_url(running["port"]))
        return 0
    stop_running_viewer()
    start_detached()
    if not wait_until_healthy(configured_port(), 3):
        print(f"The viewer did not start. See {data_dir() / 'viewer.log'}", file=sys.stderr)
        return 1
    print(viewer_url(configured_port()))
    return 0


def command_stop(arguments):
    print("Viewer stopped." if stop_running_viewer() else "The viewer was not running.")
    return 0


def command_state(arguments):
    print(json.dumps(build_state(data_dir()), indent=2))
    return 0


def command_act(arguments):
    try:
        request = json.loads(arguments[0])
        if not isinstance(request, dict):
            raise Refusal("The request must be a JSON object.")
        print(apply_action(data_dir(), request))
    except IndexError:
        print("Usage: viewer.py act '{\"action\": \"stage-down\"}'", file=sys.stderr)
        return 2
    except json.JSONDecodeError:
        print("The request is not valid JSON.", file=sys.stderr)
        return 2
    except Refusal as refusal:
        print(refusal, file=sys.stderr)
        return 1
    return 0


def command_status(arguments):
    running = read_pidfile()
    if running and process_is_alive(running["pid"]) and is_healthy(running["port"]):
        print(f"running {viewer_url(running['port'])} version {running['version']}")
        return 0
    print("not running")
    return 1


def command_serve(arguments):
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        server = ViewerServer(directory, configured_port())
    except OSError as failure:
        print(f"Cannot listen on port {configured_port()}: {failure}", file=sys.stderr)
        return 1
    pidfile_path().write_text(json.dumps({"pid": os.getpid(), "port": server.server_port, "version": plugin_version()}))
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    try:
        server.serve_forever()
    finally:
        pidfile_path().unlink(missing_ok=True)
    return 0


COMMANDS = {
    "ensure": command_ensure,
    "stop": command_stop,
    "status": command_status,
    "serve": command_serve,
    "state": command_state,
    "act": command_act,
}


def main(arguments):
    command = COMMANDS.get(arguments[1] if len(arguments) > 1 else "status")
    if command is None:
        print(f"Usage: viewer.py {' | '.join(COMMANDS)}", file=sys.stderr)
        return 2
    return command(arguments[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
