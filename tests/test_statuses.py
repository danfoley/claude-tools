import tempfile
import unittest
from pathlib import Path

import export_stats
from statuses import canonical_status


class CanonicalStatusTest(unittest.TestCase):
    def test_old_names_become_the_new_names(self):
        for old_name, new_name in (("shaky", "learning"), ("explained", "getting it")):
            with self.subTest(old_name=old_name):
                self.assertEqual(canonical_status(old_name), new_name)

    def test_new_names_stay_as_they_are(self):
        for status in ("new", "learning", "getting it", "solid", ""):
            with self.subTest(status=status):
                self.assertEqual(canonical_status(status), status)


class ExportedConceptsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.ledger_path = Path(folder.name) / "ledger.md"

    def test_exported_concepts_use_the_new_status_names(self):
        self.ledger_path.write_text("### idempotency\n- status: explained\n")
        concept = export_stats.read_concepts(self.ledger_path)[0]
        self.assertEqual(concept["status"], "getting it")

    def test_exported_concepts_carry_the_study_estimate(self):
        self.ledger_path.write_text("### idempotency\n- study: good (2026-11-05), used it once\n")
        concept = export_stats.read_concepts(self.ledger_path)[0]
        self.assertEqual(concept["study"], "good (2026-11-05), used it once")


if __name__ == "__main__":
    unittest.main()
