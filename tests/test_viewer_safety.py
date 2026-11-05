import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from pathlib import Path

import viewer

PLUGIN = Path(__file__).resolve().parents[1] / "understand-first"
LEDGER = "stage: 3\nprimary-language: PHP\n\n## Code dial\n- PHP: rung 2, clean streak 1\n\n# Concept ledger\n"


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class TemporaryDataTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)
        patched = unittest.mock.patch.dict(os.environ, {"UNDERSTAND_FIRST_DATA": str(self.data)})
        patched.start()
        self.addCleanup(patched.stop)


class PidfileTest(TemporaryDataTest):
    def write_pidfile(self, **fields):
        record = {"pid": os.getpid(), "port": 1, "version": "0.0.0", "root": "x", **fields}
        (self.data / "viewer.pid").write_text(json.dumps(record))

    def test_stop_does_not_signal_a_viewer_recorded_for_another_port(self):
        self.write_pidfile(port=free_port())
        with unittest.mock.patch("os.kill") as kill, unittest.mock.patch.dict(
            os.environ, {"UNDERSTAND_FIRST_PORT": str(free_port())}
        ):
            viewer.stop_running_viewer()
        self.assertNotIn(unittest.mock.call(os.getpid(), signal.SIGTERM), kill.call_args_list)
        self.assertTrue((self.data / "viewer.pid").exists())

    def test_stop_does_not_signal_a_process_that_is_not_answering_as_the_viewer(self):
        port = free_port()
        self.write_pidfile(port=port)
        with unittest.mock.patch("os.kill") as kill, unittest.mock.patch.dict(
            os.environ, {"UNDERSTAND_FIRST_PORT": str(port)}
        ):
            viewer.stop_running_viewer()
        self.assertNotIn(unittest.mock.call(os.getpid(), signal.SIGTERM), kill.call_args_list)

    def test_a_pidfile_naming_another_process_is_not_removed(self):
        self.write_pidfile(pid=os.getpid() + 1)
        viewer.release_pidfile()
        self.assertTrue((self.data / "viewer.pid").exists())

    def test_a_pidfile_naming_this_process_is_removed(self):
        self.write_pidfile()
        viewer.release_pidfile()
        self.assertFalse((self.data / "viewer.pid").exists())

    def test_a_pidfile_that_is_not_an_object_is_ignored(self):
        (self.data / "viewer.pid").write_text("[1]")
        self.assertIsNone(viewer.read_pidfile())

    def test_serve_records_pid_port_and_install_path_and_stop_ends_it(self):
        port = free_port()
        environment = {**os.environ, "UNDERSTAND_FIRST_PORT": str(port)}
        process = subprocess.Popen(
            [sys.executable, str(PLUGIN / "scripts" / "viewer.py"), "serve"],
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(lambda: process.poll() is None and process.kill())
        self.assertTrue(viewer.wait_until_healthy(port, 10))
        recorded = viewer.read_pidfile()
        self.assertEqual((recorded["pid"], recorded["port"], recorded["root"]), (process.pid, port, str(PLUGIN)))
        with unittest.mock.patch.dict(os.environ, {"UNDERSTAND_FIRST_PORT": str(port)}):
            viewer.stop_running_viewer()
        process.wait(timeout=10)
        self.assertFalse((self.data / "viewer.pid").exists())

    def test_a_second_viewer_does_not_take_over_a_live_viewers_pidfile(self):
        self.write_pidfile(pid=os.getppid(), port=free_port())
        before = (self.data / "viewer.pid").read_text()
        viewer.claim_pidfile(free_port())
        self.assertEqual((self.data / "viewer.pid").read_text(), before)


class VersionTest(unittest.TestCase):
    def test_the_version_survives_the_install_folder_being_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "0.1.0"
            (root / ".claude-plugin").mkdir(parents=True)
            (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": "0.1.0"}))
            with unittest.mock.patch.object(viewer, "PLUGIN_ROOT", root):
                self.assertEqual(viewer.plugin_version(), "0.1.0")
                (root / ".claude-plugin" / "plugin.json").unlink()
                self.assertEqual(viewer.plugin_version(), "0.1.0")

    def test_the_update_watcher_keeps_watching_after_a_failed_check(self):
        server = unittest.mock.Mock(handover_to=None)
        checks = [OSError("gone"), None, Path("/newer")]
        with unittest.mock.patch.object(viewer, "newer_installed_plugin", side_effect=checks), \
                unittest.mock.patch.object(viewer, "update_check_seconds", return_value=0):
            viewer.hand_over_when_a_newer_version_is_installed(server)
        self.assertEqual(server.handover_to, Path("/newer"))


class MalformedInputTest(TemporaryDataTest):
    def setUp(self):
        super().setUp()
        (self.data / "ledger.md").write_text(LEDGER)
        self.server = viewer.ViewerServer(self.data, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.shutdown)

    def shutdown(self):
        self.server.shutdown()
        self.server.server_close()

    def post(self, raw_body):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("POST", "/api/action", body=raw_body, headers={
            "Content-Type": "application/json", "X-Token": self.server.token,
        })
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_an_infinite_stage_target_is_answered_not_dropped(self):
        status, _ = self.post(b'{"action":"stage-down","to":1e999}')
        self.assertEqual(status, 200)

    def test_a_request_body_that_is_not_an_object_is_refused(self):
        for body in (b"[1]", b"null", b'"x"', b"5"):
            self.assertEqual(self.post(body)[0], 400)

    def test_absurd_rung_digits_in_the_ledger_do_not_break_the_state(self):
        (self.data / "ledger.md").write_text(LEDGER.replace("rung 2", "rung " + "9" * 5000))
        viewer.build_state(self.data)

    def test_absurd_code_line_digits_do_not_break_the_state(self):
        ledger = LEDGER + "\n### idea\n- status: shaky\n- code:\n  a.php:" + "9" * 5000 + "\n"
        (self.data / "ledger.md").write_text(ledger)
        viewer.build_state(self.data)

    def test_a_ledger_with_bad_bytes_still_builds_a_state(self):
        (self.data / "ledger.md").write_bytes(LEDGER.encode() + b"\xff\xfe\n")
        self.assertTrue(viewer.build_state(self.data)["hasLedger"])

    def test_events_that_are_not_objects_are_dropped(self):
        lines = ["null", "1", '"x"', "[1]", '{"event": "ok"}', "{broken"]
        self.assertEqual(viewer.parse_events("\n".join(lines)), [{"event": "ok"}])

    def test_an_unexpected_failure_is_answered_with_a_500(self):
        with unittest.mock.patch.object(viewer, "build_state", side_effect=RuntimeError("boom")):
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
            connection.request("GET", "/api/state", headers={"Host": f"127.0.0.1:{self.server.server_port}"})
            response = connection.getresponse()
            self.assertEqual(response.status, 500)
            self.assertFalse(json.loads(response.read())["ok"])


class StalledClientTest(unittest.TestCase):
    def test_the_handler_gives_up_on_a_stalled_client(self):
        self.assertIsNotNone(viewer.ViewerHandler.timeout)
        self.assertLessEqual(viewer.ViewerHandler.timeout, 30)

    def test_a_half_sent_request_is_dropped_by_the_server(self):
        with unittest.mock.patch.object(viewer.ViewerHandler, "timeout", 0.3):
            with tempfile.TemporaryDirectory() as folder:
                server = viewer.ViewerServer(Path(folder), 0)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                try:
                    client = socket.create_connection(("127.0.0.1", server.server_port), timeout=5)
                    client.sendall(b"GET /api/health HTTP/1.1\r\nHost: 127")
                    started = time.monotonic()
                    client.recv(1)
                    self.assertLess(time.monotonic() - started, 3)
                    client.close()
                finally:
                    server.shutdown()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()
