from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from .backend import StorageBackend
from .configuration import (
    BACKENDS_DIRECTORY,
    BackendUnavailableError,
    StorageConfiguration,
    build_backend,
    load_configuration,
    remove_configuration,
    save_configuration,
    sync_directory,
    sync_from_configuration,
)
from .discovery import Discovered, discover_backends
from .sync_state import SyncState

MAX_SETTING_LENGTH = 500
REACHABILITY_PROBE_FILE = "ledger.md"


def storage_overview(data_dir: Path, backends_directory: Path = BACKENDS_DIRECTORY) -> dict[str, Any]:
    discovered = installed_backends(backends_directory)
    return {
        "configured": configured_choice(data_dir),
        "backends": [describe(backend) for _, backend in sorted(discovered.backends.items())],
        "failures": dict(discovered.failures),
        "lastError": SyncState(sync_directory(data_dir)).last_error,
    }


def configure_storage(data_dir: Path, backend_name: str, settings: Any) -> None:
    require_text_settings(settings)
    configuration = StorageConfiguration(backend_name, dict(settings))
    require_reachable(build_backend(configuration, installed_backends(BACKENDS_DIRECTORY)))
    save_configuration(sync_directory(data_dir), configuration)


def disable_storage(data_dir: Path) -> None:
    remove_configuration(sync_directory(data_dir))


def sync_now(data_dir: Path) -> None:
    sync = sync_from_configuration(data_dir)
    if sync is None:
        raise BackendUnavailableError("No storage backend is configured")
    sync.pull()


@cache
def installed_backends(backends_directory: Path) -> Discovered:
    return discover_backends(backends_directory)


def require_reachable(backend: StorageBackend) -> None:
    try:
        backend.get(REACHABILITY_PROBE_FILE)
    except Exception as error:
        raise BackendUnavailableError(f"Could not reach the storage backend: {error}") from error


def configured_choice(data_dir: Path) -> dict[str, Any] | None:
    configuration = load_configuration(sync_directory(data_dir))
    return None if configuration is None else {"backend": configuration.backend, "settings": configuration.settings}


def describe(backend: type[StorageBackend]) -> dict[str, Any]:
    settings = [
        {"key": setting.key, "label": setting.label, "default": setting.default} for setting in backend.settings
    ]
    return {"name": backend.name, "settings": settings}


def require_text_settings(settings: Any) -> None:
    if not isinstance(settings, dict):
        raise BackendUnavailableError("Settings must be a set of names and values")
    for key, value in settings.items():
        if not (isinstance(key, str) and isinstance(value, str) and len(value) <= MAX_SETTING_LENGTH):
            raise BackendUnavailableError(f"Setting {key!r} must be text of at most {MAX_SETTING_LENGTH} characters")
