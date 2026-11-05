import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import export_stats

SCRIPT = Path(export_stats.__file__).resolve()
LEDGER = (
    "stage: 2\n\n# Concept ledger\n\n### idempotency\n- status: Solid\n- last verified: 2026-11-05\n"
    "- applied in PHP: used it in the importer\n"
    "  - email digest (PR 101) | what: retry safe\n"
    "  - plain label: with colon\n"
)


class TemporaryDataTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)
        self.ledger_path = self.data / "ledger.md"
        self.events_path = self.data / "events.jsonl"


class ExportedConceptsTest(TemporaryDataTest):
    def concept(self, ledger):
        self.ledger_path.write_text(ledger)
        return export_stats.read_concepts(self.ledger_path)[0]

    def test_applied_notes_are_exported(self):
        self.assertEqual(self.concept(LEDGER)["applied"], "PHP: used it in the importer")

    def test_example_labels_stop_at_the_pipe(self):
        self.assertEqual(self.concept(LEDGER)["exampleLabels"], "email digest (PR 101); plain label")

    def test_a_byte_order_mark_and_windows_line_endings_do_not_hide_concepts(self):
        ledger = "﻿" + LEDGER.replace("\n", "\r\n")
        self.assertEqual(self.concept(ledger)["status"], "solid")

    def test_stage_two_header_without_space_does_not_swallow_a_concept(self):
        self.assertEqual(self.concept("stage:2\n" + LEDGER)["concept"], "idempotency")

    def test_status_is_case_insensitive(self):
        self.assertEqual(self.concept(LEDGER)["status"], "solid")
        self.assertEqual(self.concept(LEDGER)["lastVerified"], "2026-11-05")


class ExportedEventsTest(TemporaryDataTest):
    def test_bad_and_non_object_lines_are_skipped(self):
        self.events_path.write_text(
            '{"date": "2026-11-05", "time": "09:00", "note": "ok"}\n'
            '{"note": "it\'s "quoted""}\n[1, 2]\n"text"\n\n'
            '{"date": "2026-11-06"}\n'
        )
        events = export_stats.read_events(self.events_path)
        self.assertEqual([event["day"] for event in events], ["2026-11-05", "2026-11-06"])

    def test_invalid_utf8_does_not_crash(self):
        self.events_path.write_bytes(b'{"date": "2026-11-05"}\n\xff\xfe\n')
        self.assertEqual(len(export_stats.read_events(self.events_path)), 1)


class ExportCommandTest(TemporaryDataTest):
    def test_isolated_script_run_writes_both_files(self):
        self.ledger_path.write_text(LEDGER)
        self.events_path.write_text('{"date": "2026-11-05"}\n')
        out = self.data / "out"
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), str(self.data), str(out)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "concepts=1 events=1")
        self.assertEqual(json.loads((out / "concepts.json").read_text())[0]["concept"], "idempotency")


if __name__ == "__main__":
    unittest.main()
