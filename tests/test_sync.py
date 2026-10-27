import tempfile
import unittest
from pathlib import Path

from storage import PushLock, StorageBackend, Sync, SyncSchedule


class BackendDownError(Exception):
    pass


class MemoryBackend(StorageBackend):
    name = "memory"

    def __init__(self):
        self.files = {}
        self.puts = []
        self.down = False

    def get(self, name):
        self.fail_when_down()
        return self.files.get(name)

    def put(self, name, text):
        self.fail_when_down()
        self.files[name] = text
        self.puts.append(name)

    def fail_when_down(self):
        if self.down:
            raise BackendDownError("the backend is down")


class FakeClock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


class Computer:
    def __init__(self, test, backend, clock):
        folders = tempfile.TemporaryDirectory()
        test.addCleanup(folders.cleanup)
        self.data = Path(folders.name) / "data"
        self.state = Path(folders.name) / "state"
        self.data.mkdir()
        self.sync = Sync(self.data, self.state, backend, clock)
        self.schedule = SyncSchedule(self.sync)

    def write(self, name, text):
        (self.data / name).write_text(text)

    def read(self, name):
        path = self.data / name
        return path.read_text() if path.exists() else None


class SyncTestCase(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryBackend()
        self.clock = FakeClock()
        self.laptop = self.computer()

    def computer(self):
        return Computer(self, self.backend, self.clock)


class PushTest(SyncTestCase):
    def test_sends_a_changed_file(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 1\n")

    def test_does_not_send_an_unchanged_file_again(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.laptop.sync.push()
        self.laptop.sync.push()
        self.assertEqual(self.backend.puts, ["ledger.md"])

    def test_sends_a_file_again_once_it_changes(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.laptop.sync.push()
        self.laptop.write("ledger.md", "stage: 2\n")
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 2\n")

    def test_ignores_files_that_do_not_exist_locally(self):
        self.laptop.sync.push()
        self.assertEqual(self.backend.puts, [])

    def test_never_sends_files_that_are_not_part_of_the_synced_set(self):
        self.laptop.write("viewer.pid", "123")
        self.laptop.sync.push()
        self.assertEqual(self.backend.puts, [])

    def test_a_failed_push_is_retried_on_the_next_push(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.backend.down = True
        with self.assertRaises(BackendDownError):
            self.laptop.sync.push()
        self.backend.down = False
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 1\n")

    def test_does_not_overwrite_a_backend_file_this_computer_has_never_synced(self):
        self.backend.files["ledger.md"] = "history from another computer\n"
        self.laptop.write("ledger.md", "a brand new ledger\n")
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["ledger.md"], "history from another computer\n")


class PullTest(SyncTestCase):
    def test_a_new_computer_receives_the_backend_files(self):
        self.backend.files["ledger.md"] = "stage: 4\n"
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("ledger.md"), "stage: 4\n")

    def test_the_backend_wins_on_the_first_sync_of_a_file(self):
        self.backend.files["ledger.md"] = "history from another computer\n"
        self.laptop.write("ledger.md", "a brand new ledger\n")
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("ledger.md"), "history from another computer\n")

    def test_replaces_an_unchanged_file_with_the_newer_backend_version(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.laptop.sync.push()
        self.backend.files["ledger.md"] = "stage: 2 from the other laptop\n"
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("ledger.md"), "stage: 2 from the other laptop\n")

    def test_pushes_local_changes_before_pulling(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.laptop.sync.push()
        self.laptop.write("ledger.md", "stage: 2 written here\n")
        self.laptop.sync.pull()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 2 written here\n")
        self.assertEqual(self.laptop.read("ledger.md"), "stage: 2 written here\n")

    def test_keeps_a_local_change_that_could_not_be_pushed(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.laptop.sync.push()
        self.laptop.write("ledger.md", "stage: 2 written here\n")
        PushLock(self.laptop.state / "push.lock", self.clock).acquire()
        self.backend.files["ledger.md"] = "stage: 9 from the other laptop\n"
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("ledger.md"), "stage: 2 written here\n")

    def test_a_pull_does_not_trigger_a_push_afterwards(self):
        self.backend.files["ledger.md"] = "stage: 4\n"
        self.laptop.sync.pull()
        self.backend.puts.clear()
        self.laptop.sync.push()
        self.assertEqual(self.backend.puts, [])

    def test_leaves_local_files_alone_when_the_backend_has_nothing(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("ledger.md"), "stage: 1\n")
        self.assertEqual(self.backend.files["ledger.md"], "stage: 1\n")


class EventsTest(SyncTestCase):
    def test_push_adds_new_local_events_to_the_backend_events(self):
        self.backend.files["events.jsonl"] = '{"event": "from other"}\n'
        self.laptop.write("events.jsonl", '{"event": "a"}\n')
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["events.jsonl"], '{"event": "from other"}\n{"event": "a"}\n')

    def test_push_sends_each_event_only_once(self):
        self.laptop.write("events.jsonl", '{"event": "a"}\n')
        self.laptop.sync.push()
        self.laptop.write("events.jsonl", '{"event": "a"}\n{"event": "b"}\n')
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["events.jsonl"], '{"event": "a"}\n{"event": "b"}\n')

    def test_push_starts_a_new_line_when_the_backend_log_ends_mid_line(self):
        self.backend.files["events.jsonl"] = '{"event": "gate-pa'
        self.laptop.write("events.jsonl", '{"event": "a"}\n')
        self.laptop.sync.push()
        self.assertEqual(self.backend.files["events.jsonl"], '{"event": "gate-pa\n{"event": "a"}\n')

    def test_events_recorded_on_two_computers_while_apart_are_both_kept(self):
        other = self.computer()
        self.laptop.write("events.jsonl", '{"event": "a"}\n')
        self.laptop.sync.push()
        other.sync.pull()
        self.backend.down = True
        self.laptop.write("events.jsonl", '{"event": "a"}\n{"event": "from laptop"}\n')
        other.write("events.jsonl", '{"event": "a"}\n{"event": "from other"}\n')
        self.backend.down = False
        other.sync.push()
        self.laptop.sync.pull()
        self.assertEqual(
            self.laptop.read("events.jsonl"),
            '{"event": "a"}\n{"event": "from other"}\n{"event": "from laptop"}\n',
        )
        self.assertEqual(self.backend.files["events.jsonl"], self.laptop.read("events.jsonl"))

    def test_events_pulled_from_the_backend_are_not_pushed_back(self):
        self.backend.files["events.jsonl"] = '{"event": "from other"}\n'
        self.laptop.sync.pull()
        self.backend.puts.clear()
        self.laptop.sync.push()
        self.assertEqual(self.backend.puts, [])

    def test_unpushed_local_events_survive_a_pull_when_the_push_is_skipped(self):
        self.laptop.write("events.jsonl", '{"event": "a"}\n')
        self.laptop.sync.push()
        self.laptop.write("events.jsonl", '{"event": "a"}\n{"event": "b"}\n')
        PushLock(self.laptop.state / "push.lock", self.clock).acquire()
        self.backend.files["events.jsonl"] = '{"event": "a"}\n{"event": "from other"}\n'
        self.laptop.sync.pull()
        self.assertEqual(self.laptop.read("events.jsonl"), '{"event": "a"}\n{"event": "from other"}\n{"event": "b"}\n')


class TickTest(SyncTestCase):
    PUSH_INTERVAL = 20 * 60
    IDLE_BEFORE_PULL = 60 * 60

    def test_the_first_tick_pushes_pending_changes(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.laptop.schedule.tick()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 1\n")

    def test_a_tick_soon_after_a_push_does_not_push_again(self):
        self.laptop.schedule.tick()
        self.laptop.write("ledger.md", "stage: 1\n")
        self.clock.now += self.PUSH_INTERVAL - 1
        self.laptop.schedule.tick()
        self.assertEqual(self.backend.puts, [])

    def test_a_tick_after_the_push_interval_pushes_new_changes(self):
        self.laptop.schedule.tick()
        self.laptop.write("ledger.md", "stage: 1\n")
        self.clock.now += self.PUSH_INTERVAL
        self.laptop.schedule.tick()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 1\n")

    def test_an_active_session_does_not_pull(self):
        self.laptop.schedule.tick()
        self.backend.files["ledger.md"] = "stage: 9 from the other laptop\n"
        self.clock.now += self.PUSH_INTERVAL
        self.laptop.schedule.tick()
        self.assertIsNone(self.laptop.read("ledger.md"))

    def test_coming_back_after_an_idle_stretch_pulls_first(self):
        self.laptop.schedule.tick()
        self.backend.files["ledger.md"] = "stage: 9 from the other laptop\n"
        self.clock.now += self.IDLE_BEFORE_PULL
        self.laptop.schedule.tick()
        self.assertEqual(self.laptop.read("ledger.md"), "stage: 9 from the other laptop\n")

    def test_idle_time_is_measured_from_the_last_tick_not_the_last_pull(self):
        self.laptop.schedule.tick()
        self.clock.now += self.IDLE_BEFORE_PULL - 1
        self.laptop.schedule.tick()
        self.clock.now += self.IDLE_BEFORE_PULL - 1
        self.backend.files["ledger.md"] = "stage: 9 from the other laptop\n"
        self.laptop.schedule.tick()
        self.assertIsNone(self.laptop.read("ledger.md"))

    def test_a_failed_push_is_not_retried_until_the_interval_has_passed(self):
        self.backend.down = True
        self.laptop.write("ledger.md", "stage: 1\n")
        with self.assertRaises(BackendDownError):
            self.laptop.schedule.tick()
        self.clock.now += 60
        self.laptop.schedule.tick()
        self.backend.down = False
        self.clock.now += self.PUSH_INTERVAL
        self.laptop.schedule.tick()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 1\n")

    def test_a_failure_is_remembered_until_a_later_tick_succeeds(self):
        self.backend.down = True
        self.laptop.write("ledger.md", "stage: 1\n")
        with self.assertRaises(BackendDownError):
            self.laptop.schedule.tick()
        self.assertIn("the backend is down", self.laptop.schedule.last_error)
        self.backend.down = False
        self.clock.now += self.PUSH_INTERVAL
        self.laptop.schedule.tick()
        self.assertIsNone(self.laptop.schedule.last_error)


class PushLockTest(SyncTestCase):
    def lock(self):
        return PushLock(self.laptop.state / "push.lock", self.clock, lease_seconds=600)

    def test_a_fresh_lock_blocks_a_second_holder(self):
        self.assertTrue(self.lock().acquire())
        self.assertFalse(self.lock().acquire())

    def test_a_released_lock_can_be_taken_again(self):
        first = self.lock()
        first.acquire()
        first.release()
        self.assertTrue(self.lock().acquire())

    def test_an_expired_lock_is_taken_over(self):
        self.lock().acquire()
        self.clock.now += 601
        self.assertTrue(self.lock().acquire())

    def test_a_lock_that_has_not_expired_yet_still_blocks(self):
        self.lock().acquire()
        self.clock.now += 599
        self.assertFalse(self.lock().acquire())

    def test_push_does_nothing_while_another_push_holds_the_lock(self):
        PushLock(self.laptop.state / "push.lock", self.clock).acquire()
        self.laptop.write("ledger.md", "stage: 1\n")
        self.assertFalse(self.laptop.sync.push())
        self.assertEqual(self.backend.puts, [])

    def test_push_takes_over_a_dead_push_after_it_expires(self):
        PushLock(self.laptop.state / "push.lock", self.clock).acquire()
        self.clock.now += 100_000
        self.laptop.write("ledger.md", "stage: 1\n")
        self.assertTrue(self.laptop.sync.push())
        self.assertEqual(self.backend.files["ledger.md"], "stage: 1\n")

    def test_the_lock_is_released_after_a_push(self):
        self.laptop.sync.push()
        self.assertTrue(self.lock().acquire())

    def test_the_lock_is_released_after_a_failed_push(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        self.backend.down = True
        with self.assertRaises(BackendDownError):
            self.laptop.sync.push()
        self.assertTrue(self.lock().acquire())


if __name__ == "__main__":
    unittest.main()
