from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path

Clock = Callable[[], float]
DEFAULT_LEASE_SECONDS = 600


class PushLock:
    def __init__(self, path: Path, clock: Clock, lease_seconds: float = DEFAULT_LEASE_SECONDS) -> None:
        self.path = path
        self.clock = clock
        self.lease_seconds = lease_seconds
        self.token = uuid.uuid4().hex

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.create_with_expiry():
            return True
        if not self.has_expired():
            return False
        self.path.unlink(missing_ok=True)
        return self.create_with_expiry()

    def release(self) -> None:
        if self.holder_token() == self.token:
            self.path.unlink(missing_ok=True)

    def create_with_expiry(self) -> bool:
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "w") as file:
            file.write(f"{self.token} {self.clock() + self.lease_seconds}")
        return True

    def holder_token(self) -> str | None:
        parts = self.read_parts()
        return parts[0] if parts else None

    def has_expired(self) -> bool:
        parts = self.read_parts()
        if parts is None:
            return self.is_older_than_the_lease()
        try:
            expiry = float(parts[1])
        except (IndexError, ValueError):
            return self.is_older_than_the_lease()
        return expiry <= self.clock() or expiry > self.clock() + self.lease_seconds

    def read_parts(self) -> list[str] | None:
        try:
            parts = self.path.read_text().split()
        except FileNotFoundError:
            return None
        return parts or None

    def is_older_than_the_lease(self) -> bool:
        try:
            return time.time() - self.path.stat().st_mtime >= self.lease_seconds
        except FileNotFoundError:
            return True
