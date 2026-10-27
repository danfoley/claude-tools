#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from storage import (
    BackendUnavailable, SyncState, data_directory, load_configuration, sync_directory, sync_from_configuration,
)
from storage.management import configure_storage, disable_storage

EXIT_OK = 0
EXIT_BACKEND_UNAVAILABLE = 2
EXIT_BACKEND_UNREACHABLE = 3
USAGE = "usage: sync.py pull | push | tick | status | disable | configure <backend> [setting=value ...]"


def main(arguments, data_dir):
    action, options = (arguments[0], arguments[1:]) if arguments else ("", [])
    handlers = {
        "pull": lambda: run_sync(data_dir, "pull"),
        "push": lambda: run_sync(data_dir, "push"),
        "tick": lambda: run_sync(data_dir, "tick"),
        "status": lambda: show_status(data_dir),
        "disable": lambda: disable(data_dir),
        "configure": lambda: configure(data_dir, options),
    }
    if action not in handlers:
        print(USAGE)
        return EXIT_BACKEND_UNAVAILABLE
    try:
        return handlers[action]()
    except BackendUnavailable as error:
        print(error)
        return EXIT_BACKEND_UNAVAILABLE
    except Exception as error:
        print(f"Could not reach the storage backend: {error}")
        return EXIT_BACKEND_UNREACHABLE


def run_sync(data_dir, action):
    sync = sync_from_configuration(data_dir)
    if sync is not None:
        getattr(sync, action)()
    return EXIT_OK


def show_status(data_dir):
    configuration = load_configuration(sync_directory(data_dir))
    if configuration is None:
        print("Storage: not configured, data stays on this computer only")
    else:
        print(f"Storage: {configuration.backend} {configuration.settings}")
        show_last_problem(data_dir)
    return EXIT_OK


def show_last_problem(data_dir):
    problem = SyncState(sync_directory(data_dir) / "sync-state.json").value("last_error")
    if problem:
        print(f"Last sync problem: {problem}")


def disable(data_dir):
    disable_storage(data_dir)
    return EXIT_OK


def configure(data_dir, options):
    if not options:
        print(USAGE)
        return EXIT_BACKEND_UNAVAILABLE
    configure_storage(data_dir, options[0], parse_settings(options[1:]))
    return EXIT_OK


def parse_settings(assignments):
    return dict(assignment.split("=", 1) for assignment in assignments)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], data_directory()))
