import os
import subprocess
import tempfile
import unittest
from pathlib import Path

STATUS = Path(__file__).resolve().parents[1] / "understand-first" / "statusline" / "status.sh"


class StatuslineTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)

    def status_line(self, ledger=None) -> str:
        if ledger is not None:
            (self.data / "ledger.md").write_bytes(ledger)
        environment = {**os.environ, "UNDERSTAND_FIRST_DATA": str(self.data)}
        result = subprocess.run(["sh", str(STATUS)], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_stage_is_shown(self):
        self.assertEqual(self.status_line(b"stage: 3\n### a\n"), "[understand:stage 3]")

    def test_byte_order_mark_is_ignored(self):
        self.assertEqual(self.status_line(b"\xef\xbb\xbfstage: 3\n"), "[understand:stage 3]")

    def test_windows_line_endings_are_ignored(self):
        self.assertEqual(self.status_line(b"stage: 3\r\n### a\r\n"), "[understand:stage 3]")

    def test_stage_without_a_space_is_read(self):
        self.assertEqual(self.status_line(b"stage:2\n"), "[understand:stage 2]")

    def test_a_missing_ledger_prints_nothing(self):
        self.assertEqual(self.status_line(None), "")

    def test_a_missing_stage_prints_nothing(self):
        self.assertEqual(self.status_line(b"# Concept ledger\n### a\n"), "")

    def test_an_empty_stage_prints_nothing(self):
        self.assertEqual(self.status_line(b"stage: \n"), "")

    def test_a_stage_that_is_not_a_number_prints_nothing(self):
        self.assertEqual(self.status_line(b"stage: 3\x1b[31m\n"), "")
        self.assertEqual(self.status_line(b"stage: banana\n"), "")


if __name__ == "__main__":
    unittest.main()
