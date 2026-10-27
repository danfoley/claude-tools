#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from storage import (
    BackendUnavailableError,
    Sync,
    SyncSchedule,
    SyncState,
    data_directory,
    load_configuration,
    sync_directory,
    sync_from_configuration,
)
from storage.management import configure_storage, disable_storage

EXIT_OK = 0
EXIT_NEEDS_ATTENTION = 2
EXIT_BACKEND_UNREACHABLE = 3
USAGE = "usage: sync.py pull | push | tick | status | disable | configure <backend> [setting=value ...]"
CONFIGURE_USAGE = "usage: sync.py configure <backend> [setting=value ...]"


class UsageError(Exception):
    pass


def main(arguments: list[str], data_dir: Path) -> int:
    action, options = (arguments[0], arguments[1:]) if arguments else ("", [])
    command = commands(data_dir, options).get(action)
    if command is None:
        print(USAGE)
        return EXIT_NEEDS_ATTENTION
    try:
        command()
    except (BackendUnavailableError, UsageError) as problem:
        print(problem)
        return EXIT_NEEDS_ATTENTION
    except Exception as problem:
        print(f"Could not reach the storage backend: {problem}")
        return EXIT_BACKEND_UNREACHABLE
    return EXIT_OK


def commands(data_dir: Path, options: list[str]) -> dict[str, Callable[[], None]]:
    return {
        "pull": lambda: with_sync(data_dir, Sync.pull),
        "push": lambda: with_sync(data_dir, Sync.push),
        "tick": lambda: with_sync(data_dir, lambda sync: SyncSchedule(sync).tick()),
        "status": lambda: show_status(data_dir),
        "disable": lambda: disable_storage(data_dir),
        "configure": lambda: configure(data_dir, options),
    }


def with_sync(data_dir: Path, action: Callable[[Sync], object]) -> None:
    sync = sync_from_configuration(data_dir)
    if sync is not None:
        action(sync)


def show_status(data_dir: Path) -> None:
    configuration = load_configuration(sync_directory(data_dir))
    if configuration is None:
        print("Storage: not configured, data stays on this computer only")
        return
    print(f"Storage: {configuration.backend} {configuration.settings}")
    problem = SyncState(sync_directory(data_dir)).last_error
    if problem:
        print(f"Last sync problem: {problem}")


def configure(data_dir: Path, options: list[str]) -> None:
    if not options:
        raise UsageError(CONFIGURE_USAGE)
    configure_storage(data_dir, options[0], parse_settings(options[1:]))


def parse_settings(assignments: list[str]) -> dict[str, str]:
    settings = {}
    for assignment in assignments:
        key, separator, value = assignment.partition("=")
        if not separator:
            raise UsageError(f"{assignment!r} is not setting=value. {CONFIGURE_USAGE}")
        settings[key] = value
    return settings


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], data_directory()))
