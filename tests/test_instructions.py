import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "understand-first"


def text(relative):
    return (PLUGIN / relative).read_text()


SKILL = text("skills/understand-first/SKILL.md")
CORE = text("hooks/core-rules.md")
MENU = text("commands/menu.md")
LEARN = text("commands/learn.md")
README = text("README.md")
ALL = {"SKILL": SKILL, "core-rules": CORE, "menu": MENU, "learn": LEARN, "README": README}


class InstructionTextTest(unittest.TestCase):
    def test_rename_or_merge_updates_work_log_and_events(self):
        self.assertIn("Renaming or merging a concept", SKILL)
        self.assertIn("- aka:", SKILL)
        self.assertRegex(SKILL, r"Renaming or merging[^\n]*work\.md")
        self.assertRegex(SKILL, r"Renaming or merging[^\n]*past events")

    def test_events_are_written_as_valid_json_with_real_time(self):
        self.assertIn("json.dumps", SKILL)
        self.assertIn("quoted heredoc", SKILL)
        self.assertIn("date +", SKILL)
        self.assertNotIn("from the timestamps in the session", SKILL)

    def test_no_unattended_push(self):
        self.assertNotRegex(SKILL, r"installs, test runs, pushes")
        self.assertIn("never a commit, push or PR", SKILL)

    def test_gate_integrity(self):
        self.assertIn("a case the learner has not been shown", SKILL)
        self.assertIn("never `getting it`", SKILL)
        self.assertIn("never skips the one-question spot-check", SKILL)
        self.assertIn("never skips the spot-check", CORE)
        self.assertIn("case the learner has not been shown", CORE)

    def test_level_is_derived_from_status(self):
        self.assertIn("level is derived from status", SKILL)
        self.assertIn("never stored", SKILL)

    def test_viewer_commands_agree(self):
        self.assertNotIn("never by editing the files by hand", MENU)
        self.assertIn("viewer button", SKILL)
        self.assertIn("targeted Edit", MENU)

    def test_export_stats_has_no_isolated_flag(self):
        for name, body in ALL.items():
            self.assertNotRegex(body, r"python3 -I[^\n]*export_stats", name)
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/export_stats.py" <data directory> <out directory>', MENU)

    def test_ledger_is_described_as_summary(self):
        for body in (SKILL, CORE, README):
            self.assertRegex(body, r"summary")
        self.assertNotRegex(README, r"injects[^\n]*(?<!summary of )your concept ledger")
        for name, body in ALL.items():
            self.assertNotRegex(body, r"(whole|full|entire) ledger (is )?(in|injected)", name)

    def test_storage_notices_go_to_the_learner_first(self):
        self.assertIn("STORAGE NOTICE", SKILL)
        self.assertIn("STORAGE PROBLEM", SKILL)

    def test_status_names_are_current(self):
        for name, body in ALL.items():
            for old in ("shaky", "explained"):
                for line in body.splitlines():
                    if f"`{old}`" in line or re.search(r"\bshaky\b", line):
                        self.assertRegex(line, r"(?i)old|older|read|ledgers", f"{name}: {line}")

    def test_delegation_respects_stages(self):
        self.assertNotIn("gates 1 to 3 (problem, concepts, design) and the teach-back explanation before any commit, push or PR still apply", SKILL)


if __name__ == "__main__":
    unittest.main()
