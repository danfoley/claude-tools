from __future__ import annotations

import signal
from collections.abc import Callable
from types import FrameType


def run_with_timeout(seconds: int, action: Callable[[], object]) -> None:
    def give_up(signal_number: int, frame: FrameType | None) -> None:
        raise TimeoutError(f"The storage backend did not answer within {seconds} seconds")

    previous = signal.signal(signal.SIGALRM, give_up)
    signal.alarm(seconds)
    try:
        action()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
