import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "understand-first" / "scripts"))

from storage import StorageBackend, StorageError
from storage.backends.folder import Backend as FolderBackend


class StorageContract:
    def make_backend(self):
        raise NotImplementedError

    def test_getting_a_missing_file_gives_none(self):
        self.assertIsNone(self.make_backend().get("ledger.md"))

    def test_put_then_get_returns_the_text(self):
        backend = self.make_backend()
        backend.put("ledger.md", "stage: 1\n")
        self.assertEqual(backend.get("ledger.md"), "stage: 1\n")

    def test_put_discards_the_previous_text(self):
        backend = self.make_backend()
        backend.put("ledger.md", "old text that is longer\n")
        backend.put("ledger.md", "new\n")
        self.assertEqual(backend.get("ledger.md"), "new\n")

    def test_an_empty_file_is_not_a_missing_file(self):
        backend = self.make_backend()
        backend.put("events.jsonl", "")
        self.assertEqual(backend.get("events.jsonl"), "")

    def test_files_are_independent(self):
        backend = self.make_backend()
        backend.put("ledger.md", "ledger")
        backend.put("work.md", "work")
        self.assertEqual(backend.get("ledger.md"), "ledger")

    def test_names_that_are_not_plain_file_names_are_refused(self):
        backend = self.make_backend()
        for name in ("../ledger.md", "sub/ledger.md", "/etc/passwd", "", ".."):
            with self.subTest(name=name):
                with self.assertRaises(StorageError):
                    backend.get(name)
                with self.assertRaises(StorageError):
                    backend.put(name, "x")


class StorageBackendTest(unittest.TestCase):
    def test_the_contract_cannot_be_used_directly(self):
        with self.assertRaises(TypeError):
            StorageBackend()


class FolderBackendTest(StorageContract, unittest.TestCase):
    def make_backend(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return FolderBackend(directory=folder.name)

    def test_declares_its_name_and_the_directory_setting(self):
        self.assertEqual(FolderBackend.name, "folder")
        self.assertEqual([setting.key for setting in FolderBackend.settings], ["directory"])

    def test_creates_the_directory_when_it_does_not_exist_yet(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = Path(parent) / "not" / "there" / "yet"
            FolderBackend(directory=str(directory)).put("ledger.md", "x")
            self.assertEqual((directory / "ledger.md").read_text(), "x")

    def test_refuses_to_start_without_a_directory(self):
        for directory in ("", "   "):
            with self.subTest(directory=directory):
                with self.assertRaises(StorageError):
                    FolderBackend(directory=directory)

    def test_put_leaves_no_temporary_file_behind(self):
        with tempfile.TemporaryDirectory() as folder:
            FolderBackend(directory=folder).put("ledger.md", "x")
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["ledger.md"])


if __name__ == "__main__":
    unittest.main()
