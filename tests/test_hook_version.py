import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "understand-first" / "hooks" / "session-start"


class PluginVersionTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.plugin = Path(folder.name) / "plugin"
        self.data = Path(folder.name) / "data"
        self.data.mkdir()
        shutil.copytree(HOOK.parent, self.plugin / "hooks")
        (self.plugin / ".claude-plugin").mkdir()

    def message_after_update_from_old_version(self, manifest):
        (self.plugin / ".claude-plugin" / "plugin.json").write_text(manifest)
        (self.data / "ledger.md").write_text("stage: 1\n")
        (self.data / "last-seen-version").write_text("0.0.1\n")
        environment = {**os.environ, "UNDERSTAND_FIRST_DATA": str(self.data), "NO_COLOR": "1"}
        payload = json.dumps({"hook_event_name": "SessionStart", "source": "startup"})
        result = subprocess.run(
            [str(self.plugin / "hooks" / "session-start")], env=environment, input=payload, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout).get("systemMessage", "")

    def test_a_one_line_manifest_is_read(self):
        message = self.message_after_update_from_old_version('{"name":"x","version":"9.9.9","description":"d"}')
        self.assertIn("updated from 0.0.1 to 9.9.9", message)

    def test_a_pretty_printed_manifest_is_read(self):
        message = self.message_after_update_from_old_version('{\n  "version": "9.9.9"\n}\n')
        self.assertIn("updated from 0.0.1 to 9.9.9", message)


if __name__ == "__main__":
    unittest.main()
