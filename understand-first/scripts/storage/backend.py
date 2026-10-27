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
    name = ""
    settings = ()

    @abstractmethod
    def get(self, name):
        ...

    @abstractmethod
    def put(self, name, text):
        ...

    @staticmethod
    def require_plain_file_name(name):
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise StorageError(f"Not a plain file name: {name!r}")
