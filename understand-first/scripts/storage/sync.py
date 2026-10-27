import os

from .push_lock import PushLock
from .sync_state import SyncState, hash_of

SYNCED_FILES = ("ledger.md", "work.md", "sources-added.md")
EVENTS_FILE = "events.jsonl"
PUSH_INTERVAL_SECONDS = 20 * 60
IDLE_BEFORE_PULL_SECONDS = 60 * 60
LAST_ACTIVITY = "last_activity"
LAST_PUSH_ATTEMPT = "last_push_attempt"
LAST_ERROR = "last_error"


class Sync:
    def __init__(self, data_directory, state_directory, backend, clock):
        self.data_directory = data_directory
        self.backend = backend
        self.clock = clock
        self.state = SyncState(state_directory / "sync-state.json")
        self.lock = PushLock(state_directory / "push.lock", clock)

    def tick(self):
        now = self.clock()
        idle_seconds = now - (self.state.value(LAST_ACTIVITY) or now)
        self.state.record_value(LAST_ACTIVITY, now)
        try:
            self.sync_if_due(now, idle_seconds)
        except Exception as error:
            self.state.record_value(LAST_ERROR, str(error))
            raise
        self.state.record_value(LAST_ERROR, None)

    def last_error(self):
        return self.state.value(LAST_ERROR)

    def sync_if_due(self, now, idle_seconds):
        if idle_seconds >= IDLE_BEFORE_PULL_SECONDS:
            self.state.record_value(LAST_PUSH_ATTEMPT, now)
            self.pull()
        elif now - (self.state.value(LAST_PUSH_ATTEMPT) or float("-inf")) >= PUSH_INTERVAL_SECONDS:
            self.state.record_value(LAST_PUSH_ATTEMPT, now)
            self.push()

    def push(self):
        if not self.lock.acquire():
            return False
        try:
            self.push_changed_files()
            self.push_new_events()
        finally:
            self.lock.release()
        return True

    def pull(self):
        self.push()
        self.pull_files_without_local_changes()
        self.pull_events()

    def push_changed_files(self):
        for name in SYNCED_FILES:
            text = self.read_local(name)
            if text is None or self.matches_last_sync(name, text) or self.is_new_here_but_known_to_backend(name):
                continue
            self.backend.put(name, text)
            self.state.record_hash(name, text)

    def push_new_events(self):
        local_lines = self.local_event_lines()
        new_events = "".join(local_lines[self.state.events_cursor():])
        if not new_events:
            return
        self.backend.put(EVENTS_FILE, ending_with_newline(self.backend.get(EVENTS_FILE) or "") + ending_with_newline(new_events))
        self.state.record_events_cursor(len(local_lines))

    def pull_files_without_local_changes(self):
        for name in SYNCED_FILES:
            remote = self.backend.get(name)
            if remote is None or self.has_unsynced_local_changes(name):
                continue
            self.write_local(name, remote)
            self.state.record_hash(name, remote)

    def pull_events(self):
        remote = self.backend.get(EVENTS_FILE)
        if remote is None:
            return
        unpushed_events = "".join(self.local_event_lines()[self.state.events_cursor():])
        self.write_local(EVENTS_FILE, ending_with_newline(remote) + unpushed_events)
        self.state.record_events_cursor(len(remote.splitlines(keepends=True)))

    def matches_last_sync(self, name, text):
        return self.state.hash_of_last_sync(name) == hash_of(text)

    def is_new_here_but_known_to_backend(self, name):
        return self.state.hash_of_last_sync(name) is None and self.backend.get(name) is not None

    def has_unsynced_local_changes(self, name):
        text = self.read_local(name)
        last_synced = self.state.hash_of_last_sync(name)
        return text is not None and last_synced is not None and last_synced != hash_of(text)

    def local_event_lines(self):
        return (self.read_local(EVENTS_FILE) or "").splitlines(keepends=True)

    def read_local(self, name):
        try:
            return (self.data_directory / name).read_text()
        except FileNotFoundError:
            return None

    def write_local(self, name, text):
        path = self.data_directory / name
        temporary = path.with_name(path.name + ".tmp")
        self.data_directory.mkdir(parents=True, exist_ok=True)
        temporary.write_text(text)
        os.replace(temporary, path)


def ending_with_newline(text):
    return text if text == "" or text.endswith("\n") else text + "\n"
