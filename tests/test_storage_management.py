import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "understand-first" / "scripts"))

from storage import BackendUnavailable, StorageConfiguration, SyncState, load_configuration, save_configuration
from storage.management import configure_storage, disable_storage, storage_overview, sync_now


class StorageManagementTest(unittest.TestCase):
    def setUp(self):
        folders = tempfile.TemporaryDirectory()
        self.addCleanup(folders.cleanup)
        self.data = Path(folders.name) / "data"
        self.cloud = Path(folders.name) / "cloud"
        self.data.mkdir()
        self.cloud.mkdir()

    def configured(self):
        return load_configuration(self.data / "sync")

    def test_the_overview_of_a_fresh_install_offers_the_folder_backend(self):
        overview = storage_overview(self.data)
        self.assertIsNone(overview["configured"])
        self.assertEqual(overview["failures"], {})
        self.assertIsNone(overview["lastError"])
        folder = next(backend for backend in overview["backends"] if backend["name"] == "folder")
        self.assertEqual(folder["settings"], [{"key": "directory", "label": "Folder to keep a copy of your data in", "default": ""}])

    def test_the_overview_shows_the_configured_backend(self):
        configure_storage(self.data, "folder", {"directory": str(self.cloud)})
        self.assertEqual(
            storage_overview(self.data)["configured"], {"backend": "folder", "settings": {"directory": str(self.cloud)}}
        )

    def test_the_overview_shows_the_last_sync_problem(self):
        SyncState(self.data / "sync" / "sync-state.json").record_value("last_error", "the backend is down")
        self.assertEqual(storage_overview(self.data)["lastError"], "the backend is down")

    def test_configuring_saves_the_choice(self):
        configure_storage(self.data, "folder", {"directory": str(self.cloud)})
        self.assertEqual(self.configured(), StorageConfiguration("folder", {"directory": str(self.cloud)}))

    def test_configuring_an_unknown_backend_saves_nothing(self):
        with self.assertRaisesRegex(BackendUnavailable, "nosuch"):
            configure_storage(self.data, "nosuch", {})
        self.assertIsNone(self.configured())

    def test_a_failed_configuration_keeps_the_previous_one(self):
        configure_storage(self.data, "folder", {"directory": str(self.cloud)})
        with self.assertRaises(BackendUnavailable):
            configure_storage(self.data, "nosuch", {})
        self.assertEqual(self.configured().backend, "folder")

    def test_settings_that_are_not_text_are_refused(self):
        for settings in ({"directory": 5}, {"directory": ["a"]}, {"directory": "x" * 501}, "directory=x", None):
            with self.subTest(settings=settings):
                with self.assertRaises(BackendUnavailable):
                    configure_storage(self.data, "folder", settings)
        self.assertIsNone(self.configured())

    def test_a_backend_that_cannot_be_reached_is_refused_and_saves_nothing(self):
        blocker = self.cloud / "blocker"
        blocker.write_text("a file where the directory should be")
        with self.assertRaisesRegex(BackendUnavailable, "Could not reach"):
            configure_storage(self.data, "folder", {"directory": str(blocker)})
        self.assertIsNone(self.configured())

    def test_a_folder_backend_without_a_folder_is_refused(self):
        with self.assertRaises(BackendUnavailable):
            configure_storage(self.data, "folder", {})
        self.assertIsNone(self.configured())

    def test_a_backend_that_cannot_start_with_these_settings_is_refused(self):
        with self.assertRaisesRegex(BackendUnavailable, "colour"):
            configure_storage(self.data, "folder", {"directory": str(self.cloud), "colour": "red"})

    def test_disabling_goes_back_to_local_only(self):
        configure_storage(self.data, "folder", {"directory": str(self.cloud)})
        disable_storage(self.data)
        self.assertIsNone(self.configured())

    def test_syncing_now_without_a_backend_says_so(self):
        with self.assertRaisesRegex(BackendUnavailable, "No storage backend"):
            sync_now(self.data)

    def test_syncing_now_brings_the_backend_files_here(self):
        (self.cloud / "ledger.md").write_text("stage: 4\n")
        configure_storage(self.data, "folder", {"directory": str(self.cloud)})
        sync_now(self.data)
        self.assertEqual((self.data / "ledger.md").read_text(), "stage: 4\n")

    def test_a_backend_that_fails_to_load_is_listed_in_the_overview(self):
        broken = self.cloud / "broken"
        broken.mkdir()
        (broken / "__init__.py").write_text("import module_that_does_not_exist\n")
        overview = storage_overview(self.data, backends_directory=self.cloud)
        self.assertIn("module_that_does_not_exist", overview["failures"]["broken"])
        self.assertEqual(overview["backends"], [])


if __name__ == "__main__":
    unittest.main()
