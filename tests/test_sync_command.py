import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import sync as sync_command
from storage import (
    BACKENDS_DIRECTORY,
    BackendUnavailableError,
    StorageConfiguration,
    build_backend,
    discover_backends,
    load_configuration,
    remove_configuration,
    save_configuration,
)

SCRIPTS = Path(__file__).resolve().parents[1] / "understand-first" / "scripts"


class TemporaryFolders(unittest.TestCase):
    def setUp(self):
        folders = tempfile.TemporaryDirectory()
        self.addCleanup(folders.cleanup)
        self.data = Path(folders.name) / "data"
        self.cloud = Path(folders.name) / "cloud"
        self.data.mkdir()
        self.cloud.mkdir()

    def run_command(self, *arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = sync_command.main(list(arguments), self.data)
        return code, output.getvalue()

    def configure_folder_backend(self):
        return self.run_command("configure", "folder", f"directory={self.cloud}")


class ConfigurationTest(TemporaryFolders):
    def test_there_is_no_configuration_until_one_is_saved(self):
        self.assertIsNone(load_configuration(self.data / "sync"))

    def test_a_saved_configuration_is_loaded_back(self):
        save_configuration(self.data / "sync", StorageConfiguration("folder", {"directory": "/somewhere"}))
        self.assertEqual(
            load_configuration(self.data / "sync"), StorageConfiguration("folder", {"directory": "/somewhere"})
        )

    def test_removing_the_configuration_returns_to_no_configuration(self):
        save_configuration(self.data / "sync", StorageConfiguration("folder", {"directory": "/somewhere"}))
        remove_configuration(self.data / "sync")
        self.assertIsNone(load_configuration(self.data / "sync"))

    def test_builds_the_configured_backend_with_its_settings(self):
        configuration = StorageConfiguration("folder", {"directory": str(self.cloud)})
        backend = build_backend(configuration, discover_backends(BACKENDS_DIRECTORY))
        backend.put("ledger.md", "x")
        self.assertEqual((self.cloud / "ledger.md").read_text(), "x")

    def test_a_backend_that_is_not_installed_is_unavailable(self):
        with self.assertRaisesRegex(BackendUnavailableError, "nosuch.*folder"):
            build_backend(StorageConfiguration("nosuch", {}), discover_backends(BACKENDS_DIRECTORY))

    def test_a_backend_that_failed_to_load_is_unavailable_with_the_reason(self):
        broken = self.cloud / "broken"
        broken.mkdir()
        (broken / "__init__.py").write_text("import module_that_does_not_exist\n")
        with self.assertRaisesRegex(BackendUnavailableError, "broken.*module_that_does_not_exist"):
            build_backend(StorageConfiguration("broken", {}), discover_backends(self.cloud))

    def test_a_setting_the_backend_does_not_declare_is_refused(self):
        with self.assertRaisesRegex(BackendUnavailableError, "colour"):
            configuration = StorageConfiguration("folder", {"directory": "/x", "colour": "red"})
            build_backend(configuration, discover_backends(BACKENDS_DIRECTORY))


class SyncCommandTest(TemporaryFolders):
    def test_does_nothing_when_no_backend_is_configured(self):
        (self.data / "ledger.md").write_text("stage: 1\n")
        self.assertEqual(self.run_command("pull"), (0, ""))
        self.assertEqual((self.data / "ledger.md").read_text(), "stage: 1\n")

    def test_configure_saves_the_choice(self):
        self.assertEqual(self.configure_folder_backend()[0], 0)
        self.assertEqual(
            load_configuration(self.data / "sync"), StorageConfiguration("folder", {"directory": str(self.cloud)})
        )

    def test_configure_refuses_an_unknown_backend_and_saves_nothing(self):
        code, message = self.run_command("configure", "nosuch")
        self.assertEqual(code, 2)
        self.assertIn("nosuch", message)
        self.assertIsNone(load_configuration(self.data / "sync"))

    def test_a_setting_without_an_equals_sign_is_a_usage_error_and_saves_nothing(self):
        code, message = self.run_command("configure", "folder", "directory")
        self.assertEqual(code, 2)
        self.assertIn("setting=value", message)
        self.assertIsNone(load_configuration(self.data / "sync"))

    def test_a_damaged_settings_file_is_explained_not_reported_as_unreachable(self):
        (self.data / "sync").mkdir()
        (self.data / "sync" / "config.json").write_text("{ not json")
        code, message = self.run_command("pull")
        self.assertEqual(code, 2)
        self.assertIn("damaged", message)

    def test_pull_brings_the_backend_files_to_this_computer(self):
        (self.cloud / "ledger.md").write_text("stage: 4\n")
        self.configure_folder_backend()
        self.assertEqual(self.run_command("pull")[0], 0)
        self.assertEqual((self.data / "ledger.md").read_text(), "stage: 4\n")

    def test_push_sends_this_computers_files_to_the_backend(self):
        (self.data / "ledger.md").write_text("stage: 2\n")
        self.configure_folder_backend()
        self.assertEqual(self.run_command("push")[0], 0)
        self.assertEqual((self.cloud / "ledger.md").read_text(), "stage: 2\n")

    def test_a_configured_backend_that_cannot_load_exits_2_with_an_explanation(self):
        save_configuration(self.data / "sync", StorageConfiguration("gone", {}))
        code, message = self.run_command("pull")
        self.assertEqual(code, 2)
        self.assertIn("gone", message)

    def test_an_unreachable_backend_exits_3_and_keeps_local_files(self):
        (self.data / "ledger.md").write_text("stage: 2\n")
        blocker = self.cloud / "blocker"
        blocker.write_text("a file where the directory should be")
        save_configuration(self.data / "sync", StorageConfiguration("folder", {"directory": str(blocker)}))
        code, message = self.run_command("push")
        self.assertEqual(code, 3)
        self.assertIn("Could not reach", message)
        self.assertEqual((self.data / "ledger.md").read_text(), "stage: 2\n")

    def test_disable_goes_back_to_local_only(self):
        self.configure_folder_backend()
        self.assertEqual(self.run_command("disable")[0], 0)
        (self.data / "ledger.md").write_text("stage: 2\n")
        self.run_command("push")
        self.assertFalse((self.cloud / "ledger.md").exists())

    def test_status_says_what_is_configured(self):
        self.assertIn("not configured", self.run_command("status")[1])
        self.configure_folder_backend()
        self.assertIn("folder", self.run_command("status")[1])

    def test_an_unknown_action_exits_2(self):
        self.assertEqual(self.run_command("explode")[0], 2)

    def test_runs_as_a_script_with_the_data_folder_from_the_environment(self):
        (self.cloud / "ledger.md").write_text("stage: 4\n")
        self.configure_folder_backend()
        environment = {**os.environ, "UNDERSTAND_FIRST_DATA": str(self.data)}
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "sync.py"), "pull"], env=environment, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.data / "ledger.md").read_text(), "stage: 4\n")


class UpgradeFromRelease080Test(TemporaryFolders):
    CONFIG = '{\n  "backend": "folder",\n  "settings": {\n    "directory": "%s"\n  }\n}'
    STATE = (
        '{"hashes": {"ledger.md": "7b91931a377b0a5c254f20d157b7f7261b8f379779961b8cbe41300bf50f473a"}, '
        '"events_cursor": 1, "last_activity": 1000.0, "last_push_attempt": 1000.0, "last_error": null}'
    )

    def setUp(self):
        super().setUp()
        (self.data / "sync").mkdir()
        (self.data / "sync" / "config.json").write_text(self.CONFIG % self.cloud)
        (self.data / "sync" / "sync-state.json").write_text(self.STATE)
        (self.data / "ledger.md").write_text("stage: 1\n")
        (self.data / "events.jsonl").write_text('{"event": "a"}\n{"event": "b"}\n')
        (self.cloud / "events.jsonl").write_text('{"event": "a"}\n')

    def test_the_saved_choice_of_backend_is_still_understood(self):
        code, message = self.run_command("status")
        self.assertEqual(code, 0)
        self.assertIn("folder", message)
        self.assertNotIn("Last sync problem", message)

    def test_a_push_continues_from_the_saved_cursor_without_repeating_events(self):
        self.assertEqual(self.run_command("push")[0], 0)
        self.assertEqual((self.cloud / "events.jsonl").read_text(), '{"event": "a"}\n{"event": "b"}\n')

    def test_a_file_that_matches_its_saved_hash_is_not_sent_again(self):
        self.run_command("push")
        self.assertFalse((self.cloud / "ledger.md").exists())

    def test_a_tick_works_with_the_saved_state(self):
        self.assertEqual(self.run_command("tick")[0], 0)
        self.assertEqual((self.cloud / "events.jsonl").read_text(), '{"event": "a"}\n{"event": "b"}\n')


class HooksTest(unittest.TestCase):
    def hooks(self):
        manifest = SCRIPTS.parent / "hooks" / "hooks.json"
        return json.loads(manifest.read_text())["hooks"]

    def commands(self, event):
        return [hook["command"] for entry in self.hooks()[event] for hook in entry["hooks"]]

    def test_every_prompt_runs_a_tick_that_does_not_make_claude_wait(self):
        hook = self.hooks()["UserPromptSubmit"][0]["hooks"][0]
        self.assertIn("sync.py", hook["command"])
        self.assertTrue(hook["command"].rstrip().endswith("tick"))
        self.assertTrue(hook["async"])

    def test_the_end_of_a_session_runs_a_final_push(self):
        command = self.commands("SessionEnd")[0]
        self.assertIn("sync.py", command)
        self.assertTrue(command.rstrip().endswith("push"))

    def test_the_session_start_hook_is_still_there(self):
        self.assertIn("session-start", self.commands("SessionStart")[0])


class TickCommandTest(TemporaryFolders):
    def test_tick_pushes_pending_changes_when_a_backend_is_configured(self):
        (self.data / "ledger.md").write_text("stage: 2\n")
        self.configure_folder_backend()
        self.assertEqual(self.run_command("tick")[0], 0)
        self.assertEqual((self.cloud / "ledger.md").read_text(), "stage: 2\n")

    def test_tick_does_nothing_when_no_backend_is_configured(self):
        self.assertEqual(self.run_command("tick"), (0, ""))

    def test_status_shows_the_last_sync_problem(self):
        blocker = self.cloud / "blocker"
        blocker.write_text("a file where the directory should be")
        (self.data / "ledger.md").write_text("stage: 2\n")
        save_configuration(self.data / "sync", StorageConfiguration("folder", {"directory": str(blocker)}))
        self.run_command("tick")
        self.assertIn("Last sync problem", self.run_command("status")[1])


class SessionStartHookTest(TemporaryFolders):
    def start_session(self):
        hook = SCRIPTS.parent / "hooks" / "session-start"
        environment = {**os.environ, "UNDERSTAND_FIRST_DATA": str(self.data)}
        result = subprocess.run([str(hook)], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_pulls_the_backend_ledger_before_reading_it(self):
        (self.cloud / "ledger.md").write_text("stage: 4\nfrom the cloud\n")
        self.configure_folder_backend()
        self.assertIn("from the cloud", self.start_session())

    def test_without_a_backend_there_is_no_storage_notice(self):
        self.assertNotIn("STORAGE PROBLEM", self.start_session())

    def test_a_backend_that_cannot_load_is_reported_and_nothing_is_disabled(self):
        save_configuration(self.data / "sync", StorageConfiguration("gone", {}))
        context = self.start_session()
        self.assertIn("STORAGE PROBLEM", context)
        self.assertIn("gone", context)
        self.assertIsNotNone(load_configuration(self.data / "sync"))


if __name__ == "__main__":
    unittest.main()
