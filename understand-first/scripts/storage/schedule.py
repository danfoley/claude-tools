from __future__ import annotations

from collections.abc import Callable

from .sync import Sync

PUSH_INTERVAL_SECONDS = 20 * 60
IDLE_BEFORE_PULL_SECONDS = 60 * 60


class SyncSchedule:
    def __init__(self, sync: Sync) -> None:
        self.sync = sync
        self.state = sync.state
        self.clock = sync.clock

    @property
    def last_error(self) -> str | None:
        return self.state.last_error

    def tick(self) -> None:
        now = self.clock()
        idle_seconds = now - (self.state.last_activity or now)
        self.state.last_activity = now
        try:
            self.sync_when_due(now, idle_seconds)
        except Exception as error:
            self.state.last_error = str(error)
            raise
        self.state.last_error = None

    def sync_when_due(self, now: float, idle_seconds: float) -> None:
        if idle_seconds >= IDLE_BEFORE_PULL_SECONDS:
            self.attempt(now, self.sync.pull)
        elif self.push_is_due(now):
            self.attempt(now, self.sync.push)

    def push_is_due(self, now: float) -> bool:
        last_attempt = self.state.last_push_attempt
        return last_attempt is None or now - last_attempt >= PUSH_INTERVAL_SECONDS

    def attempt(self, now: float, action: Callable[[], object]) -> None:
        self.state.last_push_attempt = now
        action()
