import os
from pathlib import Path

from storage.backend import Setting, StorageBackend, StorageError


class Backend(StorageBackend):
    name = "folder"
    settings = (Setting(key="directory", label="Folder to keep a copy of your data in"),)

    def __init__(self, directory):
        if not directory.strip():
            raise StorageError("Choose the folder to keep a copy of your data in")
        self.directory = Path(directory).expanduser()

    def get(self, name):
        try:
            return self.path_of(name).read_text()
        except FileNotFoundError:
            return None

    def put(self, name, text):
        path = self.path_of(name)
        temporary = path.with_name(path.name + ".tmp")
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary.write_text(text)
        os.replace(temporary, path)

    def path_of(self, name):
        self.require_plain_file_name(name)
        return self.directory / name
