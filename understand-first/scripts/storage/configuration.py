import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .discovery import discover_backends
from .sync import Sync

CONFIGURATION_FILE = "config.json"
BACKENDS_DIRECTORY = Path(__file__).resolve().parent / "backends"


class BackendUnavailable(Exception):
    pass


@dataclass
class StorageConfiguration:
    backend: str
    settings: dict = field(default_factory=dict)


def data_directory():
    configured = os.environ.get("UNDERSTAND_FIRST_DATA")
    return Path(configured) if configured else Path.home() / ".claude" / "understand-first"


def sync_directory(data_dir):
    return data_dir / "sync"


def load_configuration(directory):
    try:
        stored = json.loads((directory / CONFIGURATION_FILE).read_text())
    except FileNotFoundError:
        return None
    return StorageConfiguration(stored["backend"], stored.get("settings", {}))


def save_configuration(directory, configuration):
    directory.mkdir(parents=True, exist_ok=True)
    stored = {"backend": configuration.backend, "settings": configuration.settings}
    (directory / CONFIGURATION_FILE).write_text(json.dumps(stored, indent=2))


def remove_configuration(directory):
    (directory / CONFIGURATION_FILE).unlink(missing_ok=True)


def build_backend(configuration, discovered):
    backend_class = installed_backend(configuration.backend, discovered)
    declared = {setting.key: setting.default for setting in backend_class.settings}
    undeclared = sorted(set(configuration.settings) - set(declared))
    if undeclared:
        raise BackendUnavailable(f"Backend {configuration.backend!r} has no setting named {', '.join(undeclared)}")
    try:
        return backend_class(**{**declared, **configuration.settings})
    except Exception as error:
        raise BackendUnavailable(f"Backend {configuration.backend!r} could not start: {error}") from error


def installed_backend(name, discovered):
    if name in discovered.backends:
        return discovered.backends[name]
    if name in discovered.failures:
        raise BackendUnavailable(f"Backend {name!r} failed to load: {discovered.failures[name]}")
    available = ", ".join(sorted(discovered.backends)) or "none"
    raise BackendUnavailable(f"Backend {name!r} is not installed. Installed backends: {available}")


def sync_from_configuration(data_dir, clock=time.time):
    configuration = load_configuration(sync_directory(data_dir))
    if configuration is None:
        return None
    backend = build_backend(configuration, discover_backends(BACKENDS_DIRECTORY))
    return Sync(data_dir, sync_directory(data_dir), backend, clock)
