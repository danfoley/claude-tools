from __future__ import annotations

import importlib.util
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from .backend import Setting, StorageBackend


class InvalidBackendError(Exception):
    pass


@dataclass
class Discovered:
    backends: dict[str, type[StorageBackend]] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


def discover_backends(root: Path) -> Discovered:
    found = Discovered()
    for directory in sorted(root.iterdir()):
        if not (directory / "__init__.py").is_file():
            continue
        try:
            backend = load_backend(directory)
            reject_taken_name(backend, found.backends)
        except Exception as error:
            found.failures[directory.name] = f"{type(error).__name__}: {error}"
        else:
            found.backends[backend.name] = backend
    return found


def load_backend(directory: Path) -> type[StorageBackend]:
    module = import_package(directory)
    return require_valid(getattr(module, "Backend", None))


def import_package(directory: Path) -> ModuleType:
    module_name = f"storage_backend_{directory.name}"
    spec = importlib.util.spec_from_file_location(
        module_name, directory / "__init__.py", submodule_search_locations=[str(directory)]
    )
    if spec is None or spec.loader is None:
        raise InvalidBackendError("the directory cannot be imported as a package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def require_valid(candidate: object) -> type[StorageBackend]:
    if not (inspect.isclass(candidate) and issubclass(candidate, StorageBackend)):
        raise InvalidBackendError("the package must define a class named Backend that extends StorageBackend")
    if inspect.isabstract(candidate):
        missing = ", ".join(sorted(candidate.__abstractmethods__))
        raise InvalidBackendError(f"Backend does not implement: {missing}")
    if not (isinstance(candidate.name, str) and candidate.name.strip()):
        raise InvalidBackendError("Backend needs a non-empty name")
    require_valid_settings(candidate.settings)
    return candidate


def require_valid_settings(settings: tuple[Setting, ...]) -> None:
    if not all(isinstance(setting, Setting) for setting in settings):
        raise InvalidBackendError("settings must be a sequence of Setting")
    keys = [setting.key for setting in settings]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise InvalidBackendError(f"setting keys must be unique, repeated: {', '.join(repeated)}")


def reject_taken_name(backend: type[StorageBackend], backends: dict[str, type[StorageBackend]]) -> None:
    if backend.name in backends:
        raise InvalidBackendError(f"the name {backend.name!r} is already used by another backend")
