import json
import tempfile
import threading
import unittest
from pathlib import Path

import viewer
from storage import LocalFolder
from storage.sync_state import hash_of


def run_in_threads(count, action):
    errors = []

    def guarded(number):
        try:
            action(number)
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=guarded, args=(number,)) for number in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


class TemporaryFolderTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.directory = Path(folder.name)


class LocalFolderWritesTest(TemporaryFolderTest):
    def test_many_threads_writing_the_same_file_never_fail_and_leave_a_whole_version(self):
        folder = LocalFolder(self.directory)
        versions = [f"version {number}\n" * 200 for number in range(8)]
        errors = run_in_threads(8, lambda number: [folder.put("ledger.md", versions[number]) for _ in range(30)])
        self.assertEqual(errors, [])
        self.assertIn(folder.get("ledger.md"), versions)
        self.assertEqual([path.name for path in self.directory.iterdir()], ["ledger.md"])

    def test_windows_line_endings_survive_a_round_trip(self):
        folder = LocalFolder(self.directory)
        folder.put("ledger.md", "stage: 1\r\nviewer: on\r\n")
        self.assertEqual((self.directory / "ledger.md").read_bytes(), b"stage: 1\r\nviewer: on\r\n")
        self.assertEqual(folder.get("ledger.md"), "stage: 1\r\nviewer: on\r\n")

    def test_bytes_that_are_not_utf8_survive_a_round_trip_and_can_be_hashed(self):
        (self.directory / "ledger.md").write_bytes(b"stage: 1\n\xff\xfe\n")
        folder = LocalFolder(self.directory)
        text = folder.get("ledger.md")
        folder.put("copy.md", text)
        self.assertEqual((self.directory / "copy.md").read_bytes(), b"stage: 1\n\xff\xfe\n")
        self.assertIsInstance(hash_of(text), str)


class ViewerWritesTest(TemporaryFolderTest):
    def test_many_threads_writing_the_same_file_never_fail(self):
        path = self.directory / "ledger.md"
        errors = run_in_threads(8, lambda number: [viewer.write_atomically(path, f"{number}\n") for _ in range(30)])
        self.assertEqual(errors, [])
        self.assertEqual([entry.name for entry in self.directory.iterdir()], ["ledger.md"])

    def test_logging_an_event_appends_and_leaves_earlier_bytes_alone(self):
        path = self.directory / "events.jsonl"
        path.write_bytes(b'{"event":"x"}\r\n\xff\n')
        viewer.log_event(self.directory, "setting-changed", "reason", "note")
        content = path.read_bytes()
        self.assertTrue(content.startswith(b'{"event":"x"}\r\n\xff\n'))
        self.assertEqual(json.loads(content.splitlines()[-1])["event"], "setting-changed")

    def test_events_logged_at_the_same_time_are_all_kept(self):
        errors = run_in_threads(10, lambda number: viewer.log_event(self.directory, "e", "r", f"note {number}"))
        self.assertEqual(errors, [])
        notes = {json.loads(line)["note"] for line in (self.directory / "events.jsonl").read_text().splitlines()}
        self.assertEqual(notes, {f"note {number}" for number in range(10)})

    def test_changing_the_ledger_from_the_viewer_backs_it_up_first(self):
        (self.directory / "ledger.md").write_text("stage: 3\nstage-since: 2026-01-01\n\n# Concept ledger\n")
        viewer.stats_mode_terminal(self.directory, {})
        backups = list((self.directory / "backups").glob("ledger.md.*"))
        self.assertEqual([path.read_text() for path in backups], ["stage: 3\nstage-since: 2026-01-01\n\n# Concept ledger\n"])

    def test_a_ledger_with_bytes_that_are_not_utf8_is_not_damaged_by_a_viewer_change(self):
        (self.directory / "ledger.md").write_bytes(b"stage: 3\n\n# Concept ledger\n### a\n- in the learner's words: \xff\n")
        viewer.stats_mode_terminal(self.directory, {})
        self.assertIn(b"\xff", (self.directory / "ledger.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
