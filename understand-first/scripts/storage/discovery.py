import importlib.util
import inspect
import sys
from dataclasses import dataclass, field

from .backend import Setting, StorageBackend


class InvalidBackend(Exception):
    pass


@dataclass
class Discovered:
    backends: dict = field(default_factory=dict)
    failures: dict = field(default_factory=dict)


def discover_backends(root):
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


def load_backend(directory):
    module = import_package(directory)
    backend = getattr(module, "Backend", None)
    require_valid(backend)
    return backend


def import_package(directory):
    module_name = f"storage_backend_{directory.name}"
    spec = importlib.util.spec_from_file_location(
        module_name, directory / "__init__.py", submodule_search_locations=[str(directory)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[module_name]
        raise
    return module


def require_valid(backend):
    if not (inspect.isclass(backend) and issubclass(backend, StorageBackend)):
        raise InvalidBackend("the package must define a class named Backend that extends StorageBackend")
    if inspect.isabstract(backend):
        missing = ", ".join(sorted(backend.__abstractmethods__))
        raise InvalidBackend(f"Backend does not implement: {missing}")
    if not (isinstance(backend.name, str) and backend.name.strip()):
        raise InvalidBackend("Backend needs a non-empty name")
    require_valid_settings(backend.settings)


def require_valid_settings(settings):
    if not all(isinstance(setting, Setting) for setting in settings):
        raise InvalidBackend("settings must be a sequence of Setting")
    keys = [setting.key for setting in settings]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise InvalidBackend(f"setting keys must be unique, repeated: {', '.join(repeated)}")


def reject_taken_name(backend, backends):
    if backend.name in backends:
        raise InvalidBackend(f"the name {backend.name!r} is already used by another backend")
