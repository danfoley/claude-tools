from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .backend import StorageBackend

ENCODING = "utf-8"
KEEP_UNREADABLE_BYTES = "surrogateescape"


class LocalFolder:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def get(self, name: str) -> str | None:
        try:
            with self.path_of(name).open(encoding=ENCODING, errors=KEEP_UNREADABLE_BYTES, newline="") as file:
                return file.read()
        except FileNotFoundError:
            return None

    def put(self, name: str, text: str) -> None:
        path = self.path_of(name)
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, prefix=f".{name}.", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding=ENCODING, errors=KEEP_UNREADABLE_BYTES, newline="") as file:
                file.write(text)
            Path(temporary).replace(path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def path_of(self, name: str) -> Path:
        StorageBackend.require_plain_file_name(name)
        return self.directory / name
