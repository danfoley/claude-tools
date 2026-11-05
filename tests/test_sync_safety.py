import json
from pathlib import Path

from storage import Sync, SyncState
from storage.sync import SyncProblemError
from test_sync import SyncTestCase

LEDGER = "stage: 2\n\n### a\n- status: learning\n" * 20


def forget_sync_history(test, computer):
    (computer.state / "sync-state.json").unlink()
    computer.sync = Sync(computer.data, computer.state, test.backend, test.clock)


def synced_laptop(test):
    test.laptop.write("ledger.md", LEDGER)
    test.laptop.sync.push()
    return test.laptop


class PullGuardsTest(SyncTestCase):
    def test_an_empty_backend_ledger_does_not_replace_the_local_one(self):
        synced_laptop(self)
        self.backend.files["ledger.md"] = ""
        with self.assertRaises(SyncProblemError):
            self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("ledger.md"), LEDGER)

    def test_a_much_smaller_backend_ledger_does_not_replace_the_local_one(self):
        synced_laptop(self)
        self.backend.files["ledger.md"] = "stage: 2\n"
        with self.assertRaises(SyncProblemError):
            self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("ledger.md"), LEDGER)

    def test_a_pulled_file_first_backs_up_the_local_copy(self):
        synced_laptop(self)
        self.backend.files["ledger.md"] = LEDGER + "### b\n- status: new\n"
        self.laptop.sync.pull()
        backups = list((self.laptop.data / "backups").glob("ledger.md.*"))
        self.assertEqual([path.read_text() for path in backups], [LEDGER])

    def test_without_sync_history_the_backend_wins_but_the_local_ledger_is_backed_up_and_announced(self):
        self.backend.files["ledger.md"] = LEDGER + "### from the backend\n"
        self.laptop.write("ledger.md", LEDGER + "### from this computer\n")
        self.laptop.sync.pull()
        self.assertIn("from the backend", self.laptop.read("ledger.md"))
        backups = list((self.laptop.data / "backups").glob("ledger.md.*"))
        self.assertIn("from this computer", backups[0].read_text())
        self.assertIn("ledger.md", self.laptop.sync.notices[0])

    def test_a_lost_sync_state_keeps_local_work_in_a_backup(self):
        synced_laptop(self)
        self.laptop.write("ledger.md", LEDGER + "### new local work\n")
        forget_sync_history(self, self.laptop)
        self.laptop.sync.pull()
        backups = list((self.laptop.data / "backups").glob("ledger.md.*"))
        self.assertIn("new local work", backups[0].read_text())
        self.assertTrue(self.laptop.sync.notices)

    def test_a_new_computer_takes_the_backend_copy(self):
        self.backend.files["ledger.md"] = LEDGER
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("ledger.md"), LEDGER)


class PushGuardsTest(SyncTestCase):
    def test_an_empty_local_ledger_is_not_pushed(self):
        synced_laptop(self)
        self.laptop.write("ledger.md", "")
        with self.assertRaises(SyncProblemError):
            self.laptop.sync.push()
        self.assertEqual(self.backend.files["ledger.md"], LEDGER)

    def test_a_local_ledger_less_than_half_the_backend_size_is_not_pushed(self):
        synced_laptop(self)
        self.laptop.write("ledger.md", "stage: 2\n")
        with self.assertRaises(SyncProblemError):
            self.laptop.sync.push()
        self.assertEqual(self.backend.files["ledger.md"], LEDGER)

    def test_a_backend_that_says_a_synced_file_is_missing_is_not_overwritten(self):
        synced_laptop(self)
        del self.backend.files["ledger.md"]
        self.laptop.write("ledger.md", LEDGER + "### more\n")
        with self.assertRaises(SyncProblemError):
            self.laptop.sync.push()
        self.assertNotIn("ledger.md", self.backend.files)


class EventsMergeTest(SyncTestCase):
    def test_a_lost_sync_state_does_not_duplicate_events(self):
        self.laptop.write("events.jsonl", '{"e":1}\n{"e":2}\n')
        self.laptop.sync.push()
        self.laptop.write("events.jsonl", '{"e":1}\n{"e":2}\n{"e":3}\n')
        forget_sync_history(self, self.laptop)
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("events.jsonl").count("\n"), 3)

    def test_an_empty_backend_events_log_does_not_wipe_local_events(self):
        self.laptop.write("events.jsonl", '{"e":1}\n{"e":2}\n')
        self.laptop.sync.push()
        self.backend.files["events.jsonl"] = ""
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("events.jsonl"), '{"e":1}\n{"e":2}\n')
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["events.jsonl"], '{"e":1}\n{"e":2}\n')

    def test_pushing_events_the_backend_already_has_does_not_duplicate_them(self):
        self.backend.files["events.jsonl"] = '{"e":1}\n'
        self.laptop.write("events.jsonl", '{"e":1}\n{"e":2}\n')
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["events.jsonl"], '{"e":1}\n{"e":2}\n')

    def test_events_from_two_computers_are_both_kept(self):
        desktop = self.computer()
        self.laptop.write("events.jsonl", '{"from":"laptop"}\n')
        self.laptop.sync.push()
        desktop.write("events.jsonl", '{"from":"desktop"}\n')
        desktop.sync.pull()
        self.assertEqual(sorted(desktop.read("events.jsonl").splitlines()), ['{"from":"desktop"}', '{"from":"laptop"}'])


class SyncStateShapeTest(SyncTestCase):
    def test_a_sync_state_of_the_wrong_shape_is_replaced_by_defaults(self):
        for damaged in ('[]', '{"hashes": []}', '{"hashes": {}, "events_cursor": "x"}', "null", '"text"'):
            with self.subTest(damaged=damaged):
                folder = self.laptop.state
                folder.mkdir(exist_ok=True)
                (folder / "sync-state.json").write_text(damaged)
                state = SyncState(folder)
                self.assertEqual(state.events_cursor, 0)
                self.assertIsNone(state.hash_of_last_sync("ledger.md"))
                json.dumps(state.recorded)

    def test_the_problem_text_names_the_file_and_the_reason(self):
        synced_laptop(self)
        self.backend.files["ledger.md"] = ""
        with self.assertRaises(SyncProblemError) as problem:
            self.laptop.sync.pull()
        self.assertIn("ledger.md", str(problem.exception))
        self.assertIn("empty", str(problem.exception))


class BackupsTest(SyncTestCase):
    def test_only_the_newest_ten_backups_of_a_file_are_kept(self):
        synced_laptop(self)
        for number in range(15):
            self.backend.files["ledger.md"] = LEDGER + f"### version {number}\n"
            self.clock.now += 10
            self.laptop.sync.pull()
            self.laptop.write("ledger.md", LEDGER + f"### local {number}\n")
            self.laptop.sync.state.record_hash("ledger.md", LEDGER + f"### local {number}\n")
        self.assertLessEqual(len(list(Path(self.laptop.data / "backups").glob("ledger.md.*"))), 10)

