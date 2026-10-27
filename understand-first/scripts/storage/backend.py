from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class StorageError(Exception):
    pass


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    default: str = ""


class StorageBackend(ABC):
    name: str = ""
    settings: tuple[Setting, ...] = ()

    @abstractmethod
    def get(self, name: str) -> str | None:
        ...

    @abstractmethod
    def put(self, name: str, text: str) -> None:
        ...

    @staticmethod
    def require_plain_file_name(name: str) -> None:
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise StorageError(f"Not a plain file name: {name!r}")
