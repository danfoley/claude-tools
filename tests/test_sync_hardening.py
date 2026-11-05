import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from storage import PushLock, StorageConfiguration, SyncState, discover_backends
from storage.configuration import save_configuration
from storage.management import storage_overview
from test_sync import BackendDownError, FakeClock, SyncTestCase


class PushLockTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "push.lock"
        self.clock = FakeClock()

    def lock(self, lease_seconds=10):
        return PushLock(self.path, self.clock, lease_seconds)

    def test_a_late_release_does_not_delete_the_lock_of_its_new_owner(self):
        first, second, third = self.lock(), self.lock(), self.lock()
        first.acquire()
        self.clock.now += 11
        self.assertTrue(second.acquire())
        first.release()
        self.assertFalse(third.acquire())

    def test_the_owner_can_release_and_others_can_then_acquire(self):
        first, second = self.lock(), self.lock()
        first.acquire()
        first.release()
        self.assertTrue(second.acquire())

    def test_a_freshly_created_empty_lock_is_not_stolen(self):
        self.path.write_text("")
        self.assertFalse(self.lock().acquire())

    def test_an_old_empty_lock_is_stolen(self):
        self.path.write_text("")
        old = self.path.stat().st_mtime - 3600
        os.utime(self.path, (old, old))
        self.assertTrue(self.lock().acquire())

    def test_a_lock_taken_before_the_clock_was_set_back_does_not_stay_held(self):
        self.clock.now = 1e10
        self.lock().acquire()
        self.clock.now = 1_000
        self.assertTrue(self.lock().acquire())

    def test_a_lock_that_is_still_leased_stays_held(self):
        self.lock().acquire()
        self.clock.now += 5
        self.assertFalse(self.lock().acquire())


class SkippedPushTest(SyncTestCase):
    def test_pull_says_when_its_push_was_skipped_because_the_lock_is_held(self):
        other = PushLock(self.laptop.state / "push.lock", self.clock)
        other.acquire()
        self.laptop.sync.pull()
        self.assertTrue(any("push" in notice for notice in self.laptop.sync.notices))


class ScheduleThrottleTest(SyncTestCase):
    def test_a_skipped_push_does_not_use_up_the_throttle(self):
        self.laptop.write("ledger.md", "stage: 1\n")
        holder = PushLock(self.laptop.state / "push.lock", self.clock)
        holder.acquire()
        self.laptop.schedule.tick()
        holder.release()
        self.clock.now += 1
        self.laptop.schedule.tick()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 1\n")

    def test_a_failed_idle_pull_is_retried_on_the_next_tick(self):
        self.laptop.schedule.tick()
        self.clock.now += 2 * 3600
        self.backend.down = True
        with self.assertRaises(BackendDownError):
            self.laptop.schedule.tick()
        self.backend.down = False
        self.backend.files["ledger.md"] = "stage: 9\n"
        self.clock.now += 1
        self.laptop.schedule.tick()
        self.assertEqual(self.laptop.read("ledger.md"), "stage: 9\n")

    def test_a_clock_set_back_does_not_stop_pushes(self):
        self.clock.now = 1e9
        self.laptop.schedule.tick()
        self.clock.now = 100
        self.laptop.write("ledger.md", "stage: 2\n")
        self.laptop.schedule.tick()
        self.assertEqual(self.backend.files["ledger.md"], "stage: 2\n")


class StateMergeTest(unittest.TestCase):
    def test_a_stale_copy_does_not_overwrite_what_another_process_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = SyncState(Path(folder)), SyncState(Path(folder))
            second.events_cursor = 3
            second.record_hash("ledger.md", "text")
            first.last_activity = 5.0
            reloaded = SyncState(Path(folder))
            self.assertEqual(reloaded.events_cursor, 3)
            self.assertIsNotNone(reloaded.hash_of_last_sync("ledger.md"))
            self.assertEqual(reloaded.last_activity, 5.0)


class ConfigurationSecretsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)

    def test_the_settings_file_is_readable_by_its_owner_only(self):
        save_configuration(self.data / "sync", StorageConfiguration("folder", {"directory": "x"}))
        mode = stat.S_IMODE((self.data / "sync" / "config.json").stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_overview_hides_values_that_look_like_secrets(self):
        settings = {"directory": "x", "api_token": "abc", "Secret": "s", "password": "p", "access_key": "k"}
        save_configuration(self.data / "sync", StorageConfiguration("folder", settings))
        shown = storage_overview(self.data)["configured"]["settings"]
        self.assertEqual(shown["directory"], "x")
        for key in ("api_token", "Secret", "password", "access_key"):
            self.assertNotIn(settings[key], json.dumps(shown[key]))

    def test_the_configuration_masks_secrets_for_display(self):
        masked = StorageConfiguration("b", {"token": "abc", "directory": "x"}).masked_settings()
        self.assertEqual(masked, {"token": "********", "directory": "x"})


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def add_package(self, name, source):
        (self.root / name).mkdir()
        (self.root / name / "__init__.py").write_text(source)

    def test_a_backend_that_exits_while_importing_does_not_stop_the_others(self):
        self.add_package("a_exits", "raise SystemExit(3)\n")
        self.add_package("b_broken", "raise RuntimeError('boom')\n")
        found = discover_backends(Path(__file__).resolve().parent.parent / "understand-first/scripts/storage/backends")
        self.add_package("c_bad", "import sys\nsys.exit('bye')\n")
        found_here = discover_backends(self.root)
        self.assertEqual(set(found_here.failures), {"a_exits", "b_broken", "c_bad"})
        self.assertIn("folder", found.backends)

    def test_a_missing_backends_directory_means_no_backends(self):
        found = discover_backends(self.root / "nowhere")
        self.assertEqual((found.backends, found.failures), ({}, {}))

    def test_the_configured_backend_is_not_imported_again_on_every_sync(self):
        from storage import configuration

        configuration.installed_backends.cache_clear()
        calls = []
        original = configuration.discover_backends
        configuration.discover_backends = lambda root: calls.append(root) or original(root)
        self.addCleanup(setattr, configuration, "discover_backends", original)
        configuration.installed_backends(configuration.BACKENDS_DIRECTORY)
        configuration.installed_backends(configuration.BACKENDS_DIRECTORY)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
