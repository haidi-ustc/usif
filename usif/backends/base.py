"""The backend protocol, the backend registry and helpers shared by backends.

A backend maps one external library's structure objects to and from
:class:`~usif.model.Structure`; if it implements ``read``/``write`` it also
provides that library's file formats. Backend modules must not import their
library at module level: :meth:`Backend.accepts` recognises objects by class
name, and the library is imported only when a conversion runs.

Third-party backends register with :func:`register` or through the
``usif.backends`` entry-point group (the entry point names a ``Backend``
class or instance).
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import threading
import warnings
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Union, runtime_checkable

import numpy as np

from usif.errors import MissingDependencyError, ValidationError
from usif.model.properties import DEFAULT_SCHEMA, PropertyMap, Schema, normalize_json
from usif.model.structure import Structure
from usif.units import convert

__all__ = [
    "Backend",
    "FileBackend",
    "available",
    "backends",
    "for_object",
    "get",
    "is_instance_of",
    "register",
]

logger = logging.getLogger(__name__)

PathLike = Union[str, "os.PathLike[str]"]

ENTRY_POINT_GROUP = "usif.backends"
_BUILTIN = (
    ("usif.backends.matsimpy", "MatsimpyBackend"),
    ("usif.backends.ase", "AseBackend"),
    ("usif.backends.pymatgen", "PymatgenBackend"),
)


@runtime_checkable
class Backend(Protocol):
    """Converts one library's structure objects."""

    #: Registry name, also the library's import name (e.g. ``"ase"``).
    name: str

    def accepts(self, obj: Any) -> bool:
        """True when ``obj`` is one of this library's structure objects (no import)."""

    def to_structure(self, obj: Any, *, schema: Schema = DEFAULT_SCHEMA) -> Structure:
        """Convert a library object to a :class:`Structure`."""

    def from_structure(self, structure: Structure) -> Any:
        """Convert a :class:`Structure` to this library's object."""


@runtime_checkable
class FileBackend(Backend, Protocol):
    """A backend that also reads and writes the library's file formats."""

    def read(
        self, path: PathLike, format: Optional[str] = None, *, schema: Schema = DEFAULT_SCHEMA
    ) -> List[Structure]:
        """All structures (frames) in ``path``."""

    def write(
        self, structures: Sequence[Structure], path: PathLike, format: Optional[str] = None
    ) -> None:
        """Write ``structures`` to ``path``."""


# -- registry -------------------------------------------------------------------

_lock = threading.RLock()
_registry: Dict[str, Backend] = {}
_loaded = False


def register(backend: Any, *, replace: bool = False) -> Backend:
    """Add a backend (class or instance) to the end of the lookup order."""
    instance = backend() if isinstance(backend, type) else backend
    if not isinstance(instance, Backend) or not isinstance(getattr(instance, "name", None), str):
        raise ValidationError(f"{backend!r} does not implement the usif Backend protocol")
    with _lock:
        if instance.name in _registry and not replace:
            raise ValidationError(f"a backend named {instance.name!r} is already registered")
        _registry[instance.name] = instance
    return instance


def _load() -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
        _loaded = True
        for module, attribute in _BUILTIN:
            register(getattr(importlib.import_module(module), attribute))
        try:
            from importlib.metadata import entry_points

            points: Iterable[Any] = entry_points(group=ENTRY_POINT_GROUP)
        except Exception:  # pragma: no cover - broken environment metadata
            points = ()
        for point in points:
            try:
                register(point.load())
            except Exception as exc:  # a broken plugin must not break usif
                warnings.warn(f"ignoring usif backend {point.name!r}: {exc}", stacklevel=2)


def backends() -> List[Backend]:
    """Registered backends in lookup order (built-ins first)."""
    _load()
    with _lock:
        return list(_registry.values())


def get(name: str) -> Backend:
    _load()
    try:
        return _registry[name]
    except KeyError:
        raise ValidationError(
            f"unknown backend {name!r}; registered: {', '.join(_registry)}"
        ) from None


def available(name: str) -> bool:
    """Whether the library behind backend ``name`` is importable."""
    return importlib.util.find_spec(get(name).name) is not None


def for_object(obj: Any) -> Optional[Backend]:
    for backend in backends():
        if backend.accepts(obj):
            return backend
    return None


# -- helpers for backend implementations ------------------------------------------


def is_instance_of(obj: Any, package: str, *qualnames: str) -> bool:
    """``isinstance`` by class name, so checking never imports ``package``."""
    for cls in type(obj).__mro__:
        module = cls.__module__ or ""
        if cls.__qualname__ in qualnames and (
            module == package or module.startswith(package + ".")
        ):
            return True
    return False


def require(module: str, purpose: str, extra: Optional[str] = None) -> Any:
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise MissingDependencyError(module.split(".")[0], purpose, extra) from exc


def set_value(target: PropertyMap, name: str, value: Any, unit: Optional[str] = None) -> bool:
    """Store ``value`` if it is representable; otherwise skip it with a warning."""
    try:
        target.set(str(name), value, unit=unit)
        return True
    except ValidationError as exc:
        warnings.warn(f"skipping {name!r}: {exc}", stacklevel=3)
        return False


def value_in(source: PropertyMap, name: str, unit: str) -> Any:
    """``source[name]`` converted to ``unit``, for libraries with a fixed unit system.

    Raises :class:`ValidationError` when the stored unit cannot be converted,
    rather than handing the library a value in the wrong unit.
    """
    value = source[name]
    try:
        return convert(
            np.asarray(value, dtype=float) if np.ndim(value) else value, source.unit(name), unit
        )
    except ValidationError as exc:
        raise ValidationError(f"{name!r}: {exc}") from None


def standard_value(source: PropertyMap, name: str) -> Any:
    """``source[name]``, converted to the default-schema unit when ``name`` has one.

    Used for libraries that store bare numbers by convention (eV, eV/Å, GPa, ...).
    """
    lookup = DEFAULT_SCHEMA.atom if source.length is not None else DEFAULT_SCHEMA.structure
    spec = lookup(name)
    value = value_in(source, name, spec.unit) if spec is not None and spec.unit else source[name]
    return value.tolist() if isinstance(value, np.ndarray) else value


def plain(value: Any) -> Any:
    """Library values (NumPy, Magmom, tuples) as JSON-like Python data, if possible."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    try:
        return normalize_json(value)
    except ValidationError:
        return value
