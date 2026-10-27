import tempfile
import textwrap
import unittest
from pathlib import Path

from storage import discover_backends

GOOD_BACKEND = """
from storage.backend import Setting, StorageBackend

class Backend(StorageBackend):
    name = "{name}"
    settings = (Setting(key="bucket", label="Bucket name", default=""),)

    def __init__(self, bucket):
        self.bucket = bucket

    def get(self, name):
        return None

    def put(self, name, text):
        pass
"""


class BackendDiscoveryTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def add_backend(self, directory_name, source):
        directory = self.root / directory_name
        directory.mkdir()
        (directory / "__init__.py").write_text(textwrap.dedent(source))

    def test_finds_a_backend_in_its_own_directory(self):
        self.add_backend("s3", GOOD_BACKEND.format(name="s3"))
        found = discover_backends(self.root)
        self.assertEqual(list(found.backends), ["s3"])
        self.assertEqual(found.backends["s3"].settings[0].label, "Bucket name")
        self.assertEqual(found.failures, {})

    def test_finds_several_backends(self):
        self.add_backend("s3", GOOD_BACKEND.format(name="s3"))
        self.add_backend("dropbox", GOOD_BACKEND.format(name="dropbox"))
        self.assertEqual(sorted(discover_backends(self.root).backends), ["dropbox", "s3"])

    def test_ignores_directories_without_an_init_file_and_loose_files(self):
        (self.root / "notes").mkdir()
        (self.root / "readme.txt").write_text("hello")
        found = discover_backends(self.root)
        self.assertEqual((found.backends, found.failures), ({}, {}))

    def test_a_backend_that_fails_to_import_is_skipped_and_reported(self):
        self.add_backend("broken", "import module_that_does_not_exist\n")
        self.add_backend("s3", GOOD_BACKEND.format(name="s3"))
        found = discover_backends(self.root)
        self.assertEqual(list(found.backends), ["s3"])
        self.assertIn("module_that_does_not_exist", found.failures["broken"])

    def test_a_package_without_a_backend_class_is_reported(self):
        self.add_backend("empty", "x = 1\n")
        self.assertIn("Backend", discover_backends(self.root).failures["empty"])

    def test_a_backend_that_is_not_a_storage_backend_is_reported(self):
        self.add_backend("odd", "class Backend:\n    name = 'odd'\n    settings = ()\n")
        self.assertIn("StorageBackend", discover_backends(self.root).failures["odd"])

    def test_a_backend_missing_a_method_is_reported(self):
        self.add_backend("half", """
            from storage.backend import StorageBackend

            class Backend(StorageBackend):
                name = "half"
                settings = ()

                def get(self, name):
                    return None
            """)
        self.assertIn("put", discover_backends(self.root).failures["half"])

    def test_a_backend_without_a_name_is_reported(self):
        self.add_backend("nameless", GOOD_BACKEND.format(name=""))
        found = discover_backends(self.root)
        self.assertEqual(found.backends, {})
        self.assertIn("name", found.failures["nameless"])

    def test_a_backend_with_duplicate_setting_keys_is_reported(self):
        self.add_backend("twice", GOOD_BACKEND.format(name="twice").replace(
            'default=""),)', 'default=""), Setting(key="bucket", label="Again", default=""))'))
        self.assertIn("bucket", discover_backends(self.root).failures["twice"])

    def test_a_second_backend_with_a_taken_name_is_reported(self):
        self.add_backend("first", GOOD_BACKEND.format(name="same"))
        self.add_backend("second", GOOD_BACKEND.format(name="same"))
        found = discover_backends(self.root)
        self.assertEqual(len(found.backends), 1)
        self.assertEqual(len(found.failures), 1)

    def test_the_backends_shipped_with_the_plugin_all_load(self):
        shipped = Path(__file__).resolve().parents[1] / "understand-first" / "scripts" / "storage" / "backends"
        found = discover_backends(shipped)
        self.assertEqual(found.failures, {})
        self.assertIn("folder", found.backends)


if __name__ == "__main__":
    unittest.main()
