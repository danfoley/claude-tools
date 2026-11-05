from __future__ import annotations

from pathlib import Path

from .backend import StorageBackend
from .backups import Backups
from .local_folder import LocalFolder
from .push_lock import Clock, PushLock
from .sync_state import SyncState, hash_of

SYNCED_FILES = ("ledger.md", "work.md", "sources-added.md")
EVENTS_FILE = "events.jsonl"
SMALLEST_SAFE_FRACTION = 2


class SyncProblem(Exception):
    pass


class Sync:
    def __init__(self, data_directory: Path, state_directory: Path, backend: StorageBackend, clock: Clock) -> None:
        self.data = LocalFolder(data_directory)
        self.backend = backend
        self.clock = clock
        self.state = SyncState(state_directory)
        self.lock = PushLock(state_directory / "push.lock", clock)
        self.backups = Backups(self.data, clock)
        self.problems: list[str] = []
        self.notices: list[str] = []

    def push(self) -> bool:
        self.problems = []
        pushed = self.push_under_lock()
        self.report_problems()
        return pushed

    def pull(self) -> None:
        self.problems = []
        self.notices = []
        if not self.push_under_lock():
            self.notices.append("Another sync holds the push lock, so local changes were not sent this time.")
        self.pull_files_without_local_changes()
        self.pull_events()
        self.report_problems()

    def push_under_lock(self) -> bool:
        if not self.lock.acquire():
            return False
        try:
            self.push_changed_files()
            self.push_new_events()
        finally:
            self.lock.release()
        return True

    def report_problems(self) -> None:
        if self.problems:
            raise SyncProblem(" ".join(self.problems))

    def note_problem(self, problem: str) -> None:
        if problem not in self.problems:
            self.problems.append(problem)

    def push_changed_files(self) -> None:
        for name in SYNCED_FILES:
            text = self.data.get(name)
            if text is None or self.matches_last_sync(name, text):
                continue
            remote = self.backend.get(name)
            if self.is_unsafe_to_push(name, text, remote):
                continue
            self.backend.put(name, text)
            self.state.record_hash(name, text)

    def is_unsafe_to_push(self, name: str, text: str, remote: str | None) -> bool:
        if not text.strip():
            self.note_problem(f"The local {name} is empty, so it was not sent to the backend.")
        elif remote is None and self.state.hash_of_last_sync(name) is not None:
            self.note_problem(f"The backend says {name} is missing although it was synced before, so it was not recreated.")
        elif remote is not None and self.has_no_sync_history_and_differs(name, remote):
            pass
        elif remote and len(text) * SMALLEST_SAFE_FRACTION < len(remote):
            self.note_problem(f"The local {name} is less than half the size of the backend copy, so it was not sent.")
        else:
            return False
        return True

    def push_new_events(self) -> None:
        local_lines = self.local_event_lines()
        remote_text = self.backend.get(EVENTS_FILE)
        if remote_text is None and self.state.events_cursor > 0:
            self.note_problem(f"The backend says {EVENTS_FILE} is missing although it was synced before, so it was not recreated.")
            return
        remote_text = ending_with_newline(remote_text or "")
        new_events = lines_missing_from(local_lines, remote_text.splitlines(keepends=True))
        if new_events:
            self.backend.put(EVENTS_FILE, remote_text + "".join(new_events))
        self.state.events_cursor = len(local_lines)

    def pull_files_without_local_changes(self) -> None:
        for name in SYNCED_FILES:
            remote = self.backend.get(name)
            if remote is None or self.is_unsafe_to_pull(name, remote):
                continue
            self.backups.keep(name)
            self.data.put(name, remote)
            self.state.record_hash(name, remote)

    def is_unsafe_to_pull(self, name: str, remote: str) -> bool:
        local = self.data.get(name)
        if local is None or local == remote:
            return False
        if self.has_unsynced_local_changes(name):
            pass
        elif self.has_no_sync_history_and_differs(name, remote):
            self.notices.append(f"{name} on this computer had no sync history and differed from the backend, so the backend copy was used. The old file is saved in the backups folder.")
            return False
        elif not remote.strip():
            self.note_problem(f"The backend copy of {name} is empty, so the local file was kept.")
        elif len(remote) * SMALLEST_SAFE_FRACTION < len(local):
            self.note_problem(f"The backend copy of {name} is less than half the size of the local file, so the local file was kept.")
        else:
            return False
        return True

    def pull_events(self) -> None:
        remote = self.backend.get(EVENTS_FILE)
        if remote is None:
            return
        remote_lines = ending_with_newline(remote).splitlines(keepends=True) if remote else []
        local_only = lines_missing_from(self.local_event_lines(), remote_lines)
        self.backups.keep(EVENTS_FILE)
        self.data.put(EVENTS_FILE, "".join(remote_lines + local_only))
        self.state.events_cursor = len(remote_lines)

    def matches_last_sync(self, name: str, text: str) -> bool:
        return self.state.hash_of_last_sync(name) == hash_of(text)

    def has_unsynced_local_changes(self, name: str) -> bool:
        text = self.data.get(name)
        last_synced = self.state.hash_of_last_sync(name)
        return text is not None and last_synced is not None and last_synced != hash_of(text)

    def has_no_sync_history_and_differs(self, name: str, remote: str) -> bool:
        text = self.data.get(name)
        return text is not None and self.state.hash_of_last_sync(name) is None and text != remote

    def local_event_lines(self) -> list[str]:
        return ending_with_newline(self.data.get(EVENTS_FILE) or "").splitlines(keepends=True) if self.data.get(EVENTS_FILE) else []


def lines_missing_from(lines: list[str], existing_lines: list[str]) -> list[str]:
    existing = {ending_with_newline(line) for line in existing_lines}
    return [ending_with_newline(line) for line in lines if ending_with_newline(line) not in existing]


def ending_with_newline(text: str) -> str:
    return text if text == "" or text.endswith("\n") else text + "\n"
