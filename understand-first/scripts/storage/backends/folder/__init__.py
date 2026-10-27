from __future__ import annotations

from pathlib import Path

from storage.backend import Setting, StorageBackend, StorageError
from storage.local_folder import LocalFolder


class Backend(StorageBackend):
    name = "folder"
    settings = (Setting(key="directory", label="Folder to keep a copy of your data in"),)

    def __init__(self, directory: str) -> None:
        if not directory.strip():
            raise StorageError("Choose the folder to keep a copy of your data in")
        self.folder = LocalFolder(Path(directory).expanduser())

    def get(self, name: str) -> str | None:
        return self.folder.get(name)

    def put(self, name: str, text: str) -> None:
        self.folder.put(name, text)
