from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .backend import StorageBackend
from .discovery import Discovered, discover_backends
from .local_folder import LocalFolder
from .push_lock import Clock
from .sync import Sync

CONFIGURATION_FILE = "config.json"
BACKENDS_DIRECTORY = Path(__file__).resolve().parent / "backends"


class BackendUnavailableError(Exception):
    pass


@dataclass
class StorageConfiguration:
    backend: str
    settings: dict[str, str] = field(default_factory=dict)


def data_directory() -> Path:
    configured = os.environ.get("UNDERSTAND_FIRST_DATA")
    return Path(configured) if configured else Path.home() / ".claude" / "understand-first"


def sync_directory(data_dir: Path) -> Path:
    return data_dir / "sync"


def load_configuration(directory: Path) -> StorageConfiguration | None:
    stored = LocalFolder(directory).get(CONFIGURATION_FILE)
    if stored is None:
        return None
    try:
        parsed = json.loads(stored)
        return StorageConfiguration(parsed["backend"], parsed.get("settings", {}))
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise BackendUnavailableError(
            f"The storage settings file is damaged ({error!r}). Run sync.py disable to start again."
        ) from error


def save_configuration(directory: Path, configuration: StorageConfiguration) -> None:
    stored = {"backend": configuration.backend, "settings": configuration.settings}
    LocalFolder(directory).put(CONFIGURATION_FILE, json.dumps(stored, indent=2))


def remove_configuration(directory: Path) -> None:
    (directory / CONFIGURATION_FILE).unlink(missing_ok=True)


def build_backend(configuration: StorageConfiguration, discovered: Discovered) -> StorageBackend:
    backend_class = installed_backend(configuration.backend, discovered)
    declared = {setting.key: setting.default for setting in backend_class.settings}
    undeclared = sorted(set(configuration.settings) - set(declared))
    if undeclared:
        raise BackendUnavailableError(f"Backend {configuration.backend!r} has no setting named {', '.join(undeclared)}")
    create_backend: Callable[..., StorageBackend] = backend_class
    try:
        return create_backend(**{**declared, **configuration.settings})
    except Exception as error:
        raise BackendUnavailableError(f"Backend {configuration.backend!r} could not start: {error}") from error


def installed_backend(name: str, discovered: Discovered) -> type[StorageBackend]:
    if name in discovered.backends:
        return discovered.backends[name]
    if name in discovered.failures:
        raise BackendUnavailableError(f"Backend {name!r} failed to load: {discovered.failures[name]}")
    available = ", ".join(sorted(discovered.backends)) or "none"
    raise BackendUnavailableError(f"Backend {name!r} is not installed. Installed backends: {available}")


def sync_from_configuration(data_dir: Path, clock: Clock = time.time) -> Sync | None:
    configuration = load_configuration(sync_directory(data_dir))
    if configuration is None:
        return None
    backend = build_backend(configuration, discover_backends(BACKENDS_DIRECTORY))
    return Sync(data_dir, sync_directory(data_dir), backend, clock)
