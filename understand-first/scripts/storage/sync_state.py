from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .local_folder import LocalFolder

STATE_FILE = "sync-state.json"


def hash_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class SyncState:
    def __init__(self, directory: Path) -> None:
        self.folder = LocalFolder(directory)
        self.recorded: dict[str, Any] = self.load()

    def hash_of_last_sync(self, name: str) -> str | None:
        last_hash: str | None = self.recorded["hashes"].get(name)
        return last_hash

    def record_hash(self, name: str, text: str) -> None:
        self.recorded["hashes"][name] = hash_of(text)
        self.save()

    @property
    def events_cursor(self) -> int:
        cursor: int = self.recorded["events_cursor"]
        return cursor

    @events_cursor.setter
    def events_cursor(self, cursor: int) -> None:
        self.record("events_cursor", cursor)

    @property
    def last_activity(self) -> float | None:
        moment: float | None = self.recorded.get("last_activity")
        return moment

    @last_activity.setter
    def last_activity(self, moment: float) -> None:
        self.record("last_activity", moment)

    @property
    def last_push_attempt(self) -> float | None:
        moment: float | None = self.recorded.get("last_push_attempt")
        return moment

    @last_push_attempt.setter
    def last_push_attempt(self, moment: float) -> None:
        self.record("last_push_attempt", moment)

    @property
    def last_error(self) -> str | None:
        problem: str | None = self.recorded.get("last_error")
        return problem

    @last_error.setter
    def last_error(self, problem: str | None) -> None:
        self.record("last_error", problem)

    def record(self, key: str, value: Any) -> None:
        self.recorded[key] = value
        self.save()

    def load(self) -> dict[str, Any]:
        try:
            return {"hashes": {}, "events_cursor": 0, **json.loads(self.folder.get(STATE_FILE) or "")}
        except (ValueError, TypeError):
            return {"hashes": {}, "events_cursor": 0}

    def save(self) -> None:
        self.folder.put(STATE_FILE, json.dumps(self.recorded))
