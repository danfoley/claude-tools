import tempfile
import unittest
from pathlib import Path

import migrate_ledger

HEAD = "stage: 1\n\n## Code dial\n- PHP: rung 1, clean streak 0\n\n# Concept ledger\n\n### idempotency\n- status: learning\n- examples:\n"


def example(title, path, lang=None):
    language_line = f"    lang: {lang}\n" if lang else ""
    return f"  - {title} | what: w | where: x | why: y\n{language_line}    code: {path}:3\n    >> $line;\n"


def ledger_of(*examples):
    return HEAD + "".join(examples)


class MigrateLedgerTextTest(unittest.TestCase):
    def test_tags_each_untagged_example_from_the_ending_of_its_code_file(self):
        migrated = migrate_ledger.migrate_text(ledger_of(example("a", "src/A.php"), example("b", "tools/b.py")))
        self.assertIn("    lang: PHP\n    code: src/A.php:3", migrated)
        self.assertIn("    lang: Python\n    code: tools/b.py:3", migrated)

    def test_running_it_twice_changes_nothing_more(self):
        once = migrate_ledger.migrate_text(ledger_of(example("a", "src/A.php")))
        self.assertEqual(migrate_ledger.migrate_text(once), once)

    def test_an_example_that_already_has_a_language_is_left_alone(self):
        text = ledger_of(example("a", "src/A.php", lang="Rust"))
        self.assertEqual(migrate_ledger.migrate_text(text), text)

    def test_an_ending_it_does_not_know_is_left_untagged(self):
        text = ledger_of(example("a", "services/composer.json"))
        self.assertEqual(migrate_ledger.migrate_text(text), text)


class MigrateLedgerFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.ledger = self.directory / "ledger.md"

    def test_rewrites_the_ledger_and_keeps_a_backup_of_the_old_one(self):
        original = ledger_of(example("a", "src/A.php"))
        self.ledger.write_text(original)

        migrate_ledger.migrate_directory(self.directory)

        self.assertIn("lang: PHP", self.ledger.read_text())
        backups = list((self.directory / "backups").glob("ledger.md.*"))
        self.assertEqual([backup.read_text() for backup in backups], [original])

    def test_writes_nothing_when_there_is_nothing_to_tag(self):
        self.ledger.write_text(ledger_of(example("a", "src/A.php", lang="PHP")))

        migrate_ledger.migrate_directory(self.directory)

        self.assertFalse((self.directory / "backups").exists())

    def test_does_not_create_a_ledger_that_is_not_there(self):
        migrate_ledger.migrate_directory(self.directory)

        self.assertFalse(self.ledger.exists())


if __name__ == "__main__":
    unittest.main()
