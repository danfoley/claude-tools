import sys
import unittest
from pathlib import Path

SCRIPTS = str(Path(__file__).resolve().parents[1] / "understand-first" / "scripts")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


class ScriptsPathTest(unittest.TestCase):
    def test_plugin_scripts_can_be_imported_without_pythonpath(self):
        import ledger_parse

        self.assertTrue(callable(ledger_parse.parse_ledger))


if __name__ == "__main__":
    unittest.main()
