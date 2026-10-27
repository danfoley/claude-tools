from functools import lru_cache

from .configuration import (
    BACKENDS_DIRECTORY, BackendUnavailable, StorageConfiguration, build_backend, load_configuration,
    remove_configuration, save_configuration, sync_directory, sync_from_configuration,
)
from .discovery import discover_backends
from .sync_state import SyncState

MAX_SETTING_LENGTH = 500


def storage_overview(data_dir, backends_directory=BACKENDS_DIRECTORY):
    discovered = installed_backends(backends_directory)
    return {
        "configured": configured_choice(data_dir),
        "backends": [describe(backend) for _, backend in sorted(discovered.backends.items())],
        "failures": dict(discovered.failures),
        "lastError": SyncState(sync_directory(data_dir) / "sync-state.json").value("last_error"),
    }


def configure_storage(data_dir, backend_name, settings):
    require_text_settings(settings)
    configuration = StorageConfiguration(backend_name, dict(settings))
    require_reachable(build_backend(configuration, installed_backends(BACKENDS_DIRECTORY)))
    save_configuration(sync_directory(data_dir), configuration)


def disable_storage(data_dir):
    remove_configuration(sync_directory(data_dir))


def sync_now(data_dir):
    sync = sync_from_configuration(data_dir)
    if sync is None:
        raise BackendUnavailable("No storage backend is configured")
    sync.pull()


@lru_cache(maxsize=None)
def installed_backends(backends_directory):
    return discover_backends(backends_directory)


def require_reachable(backend):
    try:
        backend.get("ledger.md")
    except Exception as error:
        raise BackendUnavailable(f"Could not reach the storage backend: {error}") from error


def configured_choice(data_dir):
    configuration = load_configuration(sync_directory(data_dir))
    return None if configuration is None else {"backend": configuration.backend, "settings": configuration.settings}


def describe(backend):
    settings = [{"key": setting.key, "label": setting.label, "default": setting.default} for setting in backend.settings]
    return {"name": backend.name, "settings": settings}


def require_text_settings(settings):
    if not isinstance(settings, dict):
        raise BackendUnavailable("Settings must be a set of names and values")
    for key, value in settings.items():
        if not (isinstance(key, str) and isinstance(value, str) and len(value) <= MAX_SETTING_LENGTH):
            raise BackendUnavailable(f"Setting {key!r} must be text of at most {MAX_SETTING_LENGTH} characters")
