import re

from statuses import canonical_status

APPLIED_PREFIX = "- applied in "
SOURCE_PREFIX = "- source: "
SOURCE_FIELD_COUNT = 4
WEB_LINK_PREFIXES = ("https://", "http://")
LANGUAGE_HEADER_PREFIX = "    lang: "
CODE_HEADER_PREFIX = "    code: "
CODE_LINE_PREFIX = "    > "
CODE_HIGHLIGHT_PREFIX = "    >> "
CODE_LINE_PREFIXES = (CODE_LINE_PREFIX, CODE_HIGHLIGHT_PREFIX)
CODE_HEADER = re.compile(r"^(?P<path>.+):(?P<start>\d{1,9})$")
DIAL_LINE = re.compile(r"^- (?P<language>.+?): rung (?P<rung>\d{1,9}), clean streak (?P<streak>\d{1,9})$")


def header_end(lines):
    return next((index for index, line in enumerate(lines) if line.startswith("#")), len(lines))


def parse_header(lines):
    header = {}
    for line in lines[: header_end(lines)]:
        key, separator, value = line.partition(":")
        if separator and key.strip():
            header[key.strip()] = value.strip()
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


def source_fields(text: str) -> list[str]:
    fields = [part.strip() for part in text.split(" | ")][:SOURCE_FIELD_COUNT]
    return fields + [""] * (SOURCE_FIELD_COUNT - len(fields))


def parse_source(text: str) -> dict[str, str]:
    title, url, kind, checked = source_fields(text)
    return {
        "title": title,
        "url": url if url.startswith(WEB_LINK_PREFIXES) else "",
        "kind": kind,
        "checked": checked.removeprefix("checked ").strip(),
    }


def parse_code_header(text: str):
    found = CODE_HEADER.match(text.strip())
    if not found:
        return None
    return {"path": found["path"], "start": int(found["start"]), "lines": []}


def parse_code_line(line: str) -> dict:
    highlight = line.startswith(CODE_HIGHLIGHT_PREFIX)
    prefix = CODE_HIGHLIGHT_PREFIX if highlight else CODE_LINE_PREFIX
    return {"text": line[len(prefix):], "highlight": highlight}


CONCEPT_FIELD_PREFIXES = {
    "- status: ": "status",
    "- last verified: ": "verified",
    "- in the learner's words: ": "words",
    "- recall question: ": "recall",
    "- study: ": "study",
}


def new_concept(name):
    return {
        "name": name, "status": "", "verified": "", "words": "", "recall": "", "study": "",
        "examples": 0, "exampleNotes": [], "exampleCode": [], "exampleLanguages": [], "applied": {}, "sources": [],
    }


def continues_code_snapshot(concept, line):
    snapshots = concept["exampleCode"]
    return bool(snapshots and snapshots[-1]) and line.startswith(CODE_LINE_PREFIXES)


def read_field(concept, line):
    for prefix, field in CONCEPT_FIELD_PREFIXES.items():
        if line.startswith(prefix):
            concept[field] = line[len(prefix):].strip()


def parse_concepts(lines):
    concepts = []
    for line in lines:
        if line.startswith("### "):
            concepts.append(new_concept(line[4:].strip()))
        elif concepts and line.startswith("  - "):
            concepts[-1]["examples"] += 1
            concepts[-1]["exampleNotes"].append(line[len("  - "):].strip())
            concepts[-1]["exampleCode"].append(None)
            concepts[-1]["exampleLanguages"].append("")
        elif concepts and concepts[-1]["exampleLanguages"] and line.startswith(LANGUAGE_HEADER_PREFIX):
            concepts[-1]["exampleLanguages"][-1] = line[len(LANGUAGE_HEADER_PREFIX):].strip()
        elif concepts and concepts[-1]["exampleCode"] and line.startswith(CODE_HEADER_PREFIX):
            concepts[-1]["exampleCode"][-1] = parse_code_header(line[len(CODE_HEADER_PREFIX):])
        elif concepts and continues_code_snapshot(concepts[-1], line):
            concepts[-1]["exampleCode"][-1]["lines"].append(parse_code_line(line))
        elif concepts and line.startswith(APPLIED_PREFIX):
            language, _, note = line[len(APPLIED_PREFIX):].partition(": ")
            if note.strip():
                concepts[-1]["applied"][language.strip()] = note.strip()
        elif concepts and line.startswith(SOURCE_PREFIX):
            concepts[-1]["sources"].append(parse_source(line[len(SOURCE_PREFIX):]))
        elif concepts:
            read_field(concepts[-1], line)
    for concept in concepts:
        concept["status"] = canonical_status(concept["status"])
    return concepts


def ledger_lines(text):
    return text.removeprefix("\ufeff").replace("\r\n", "\n").split("\n")


def parse_ledger(text):
    lines = ledger_lines(text)
    return {"header": parse_header(lines), "dial": parse_dial(lines), "concepts": parse_concepts(lines)}
