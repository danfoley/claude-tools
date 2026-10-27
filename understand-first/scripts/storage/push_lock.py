from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

Clock = Callable[[], float]
DEFAULT_LEASE_SECONDS = 600


class PushLock:
    def __init__(self, path: Path, clock: Clock, lease_seconds: float = DEFAULT_LEASE_SECONDS) -> None:
        self.path = path
        self.clock = clock
        self.lease_seconds = lease_seconds

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.create_with_expiry():
            return True
        if not self.has_expired():
            return False
        self.path.unlink(missing_ok=True)
        return self.create_with_expiry()

    def release(self) -> None:
        self.path.unlink(missing_ok=True)

    def create_with_expiry(self) -> bool:
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "w") as file:
            file.write(str(self.clock() + self.lease_seconds))
        return True

    def has_expired(self) -> bool:
        try:
            return float(self.path.read_text()) <= self.clock()
        except (FileNotFoundError, ValueError):
            return True
