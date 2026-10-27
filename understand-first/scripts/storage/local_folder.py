from __future__ import annotations

from pathlib import Path

from .backend import StorageBackend

ENCODING = "utf-8"


class LocalFolder:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def get(self, name: str) -> str | None:
        try:
            return self.path_of(name).read_text(encoding=ENCODING)
        except FileNotFoundError:
            return None

    def put(self, name: str, text: str) -> None:
        path = self.path_of(name)
        temporary = path.with_name(path.name + ".tmp")
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary.write_text(text, encoding=ENCODING)
        temporary.replace(path)

    def path_of(self, name: str) -> Path:
        StorageBackend.require_plain_file_name(name)
        return self.directory / name
