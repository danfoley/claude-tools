import json
import re
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
BADGE_VERSION = re.compile(r"img\.shields\.io/badge/understand--first-(\d+\.\d+\.\d+)-")


class VersionBadgeTest(unittest.TestCase):
    def test_the_readme_badge_shows_the_plugin_version(self):
        self.assertEqual(self.plugin_version(), self.badge_version())

    def plugin_version(self):
        manifest = REPOSITORY / "understand-first" / ".claude-plugin" / "plugin.json"
        return json.loads(manifest.read_text())["version"]

    def badge_version(self):
        match = BADGE_VERSION.search((REPOSITORY / "README.md").read_text())
        self.assertIsNotNone(match, "README.md has no static understand-first version badge")
        return match.group(1)


if __name__ == "__main__":
    unittest.main()
