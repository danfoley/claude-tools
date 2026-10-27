#!/usr/bin/env python3
import json
import sys
from pathlib import Path

LEDGER_FIELDS = {
    "status": "status",
    "last verified": "lastVerified",
    "applied": "applied",
    "in the learner's words": "words",
    "recall question": "recallQuestion",
}
EXAMPLE_PREFIX = "  - "


def main():
    data_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    concepts = read_concepts(data_dir / "ledger.md")
    events = read_events(data_dir / "events.jsonl")
    write_json(out_dir / "concepts.json", concepts)
    write_json(out_dir / "events.json", events)
    print(f"concepts={len(concepts)} events={len(events)}")


def read_concepts(ledger_path):
    if not ledger_path.exists():
        return []
    concepts = []
    for line in ledger_path.read_text().splitlines():
        if line.startswith("### "):
            concepts.append(empty_concept(line[4:].strip()))
        elif concepts and line.startswith(EXAMPLE_PREFIX):
            concepts[-1]["examples"].append(line[len(EXAMPLE_PREFIX):].strip())
        elif concepts and line.startswith("- "):
            add_field(concepts[-1], line[2:])
    return [with_example_summary(concept) for concept in concepts]


def empty_concept(name):
    row = dict.fromkeys(LEDGER_FIELDS.values(), "")
    row["concept"] = name
    row["examples"] = []
    return row


def with_example_summary(concept):
    labels = [example.partition(":")[0] for example in concept["examples"]]
    return {**concept, "exampleCount": len(labels), "exampleLabels": "; ".join(labels)}


def add_field(concept, line):
    label, _, value = line.partition(":")
    field = LEDGER_FIELDS.get(label.strip())
    if field:
        concept[field] = value.strip()


def read_events(events_path):
    if not events_path.exists():
        return []
    lines = [line for line in events_path.read_text().splitlines() if line.strip()]
    return [event_row(json.loads(line)) for line in lines]


def event_row(event):
    row = {key: ("" if value is None else value) for key, value in event.items()}
    row["day"] = row.get("date", "")
    row["timestamp"] = f"{row.get('date', '')}T{row.get('time', '00:00')}"
    return row


def write_json(path, rows):
    path.write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
