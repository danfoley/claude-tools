#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ledger_parse

EXAMPLE_LABEL_SEPARATOR = " | "


def main():
    data_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    concepts = read_concepts(data_dir / "ledger.md")
    events = read_events(data_dir / "events.jsonl")
    write_json(out_dir / "concepts.json", concepts)
    write_json(out_dir / "events.json", events)
    print(f"concepts={len(concepts)} events={len(events)}")


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def read_concepts(ledger_path):
    if not ledger_path.exists():
        return []
    return [concept_row(concept) for concept in ledger_parse.parse_ledger(read_text(ledger_path))["concepts"]]


def concept_row(concept):
    return {
        "concept": concept["name"],
        "status": concept["status"],
        "study": concept["study"],
        "lastVerified": concept["verified"],
        "applied": applied_summary(concept["applied"]),
        "words": concept["words"],
        "recallQuestion": concept["recall"],
        "examples": concept["exampleNotes"],
        "exampleCount": concept["examples"],
        "exampleLabels": "; ".join(example_label(note) for note in concept["exampleNotes"]),
    }


def applied_summary(applied):
    return "; ".join(f"{language}: {note}" for language, note in applied.items())


def example_label(note):
    return note.partition(EXAMPLE_LABEL_SEPARATOR)[0] if EXAMPLE_LABEL_SEPARATOR in note else note.partition(":")[0]


def read_events(events_path):
    if not events_path.exists():
        return []
    lines = [line for line in read_text(events_path).splitlines() if line.strip()]
    return [event_row(event) for event in map(parse_event, lines) if event is not None]


def parse_event(line):
    try:
        event = json.loads(line)
    except ValueError:
        return None
    return event if isinstance(event, dict) else None


def event_row(event):
    row = {key: ("" if value is None else value) for key, value in event.items()}
    row["day"] = row.get("date", "")
    row["timestamp"] = f"{row.get('date', '')}T{row.get('time', '00:00')}"
    return row


def write_json(path, rows):
    path.write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
