from __future__ import annotations

from pathlib import Path

from .backend import StorageBackend
from .local_folder import LocalFolder
from .push_lock import Clock, PushLock
from .sync_state import SyncState, hash_of

SYNCED_FILES = ("ledger.md", "work.md", "sources-added.md")
EVENTS_FILE = "events.jsonl"


class Sync:
    def __init__(self, data_directory: Path, state_directory: Path, backend: StorageBackend, clock: Clock) -> None:
        self.data = LocalFolder(data_directory)
        self.backend = backend
        self.clock = clock
        self.state = SyncState(state_directory)
        self.lock = PushLock(state_directory / "push.lock", clock)

    def push(self) -> bool:
        if not self.lock.acquire():
            return False
        try:
            self.push_changed_files()
            self.push_new_events()
        finally:
            self.lock.release()
        return True

    def pull(self) -> None:
        self.push()
        self.pull_files_without_local_changes()
        self.pull_events()

    def push_changed_files(self) -> None:
        for name in SYNCED_FILES:
            text = self.data.get(name)
            if text is None or self.matches_last_sync(name, text) or self.is_new_here_but_known_to_backend(name):
                continue
            self.backend.put(name, text)
            self.state.record_hash(name, text)

    def push_new_events(self) -> None:
        local_lines = self.local_event_lines()
        new_events = "".join(local_lines[self.state.events_cursor:])
        if not new_events:
            return
        backend_events = ending_with_newline(self.backend.get(EVENTS_FILE) or "")
        self.backend.put(EVENTS_FILE, backend_events + ending_with_newline(new_events))
        self.state.events_cursor = len(local_lines)

    def pull_files_without_local_changes(self) -> None:
        for name in SYNCED_FILES:
            remote = self.backend.get(name)
            if remote is None or self.has_unsynced_local_changes(name):
                continue
            self.data.put(name, remote)
            self.state.record_hash(name, remote)

    def pull_events(self) -> None:
        remote = self.backend.get(EVENTS_FILE)
        if remote is None:
            return
        unpushed_events = "".join(self.local_event_lines()[self.state.events_cursor:])
        self.data.put(EVENTS_FILE, ending_with_newline(remote) + unpushed_events)
        self.state.events_cursor = len(remote.splitlines(keepends=True))

    def matches_last_sync(self, name: str, text: str) -> bool:
        return self.state.hash_of_last_sync(name) == hash_of(text)

    def is_new_here_but_known_to_backend(self, name: str) -> bool:
        return self.state.hash_of_last_sync(name) is None and self.backend.get(name) is not None

    def has_unsynced_local_changes(self, name: str) -> bool:
        text = self.data.get(name)
        last_synced = self.state.hash_of_last_sync(name)
        return text is not None and last_synced is not None and last_synced != hash_of(text)

    def local_event_lines(self) -> list[str]:
        return (self.data.get(EVENTS_FILE) or "").splitlines(keepends=True)


def ending_with_newline(text: str) -> str:
    return text if text == "" or text.endswith("\n") else text + "\n"
