"""Single-structure input and output: the native formats and every backend format.

* ``.usif``: format-7 records (:mod:`usif.codec.record`); records written by
  USIF 0.8 and earlier (formats 5/6) are read transparently;
* ``.json`` / ``.usif.json``: the JSON document (:mod:`usif.codec.jsondoc`);
* anything else: the first available backend that reads or writes it
  (matsimpy, ASE, pymatgen, then plugins), or the one named by ``backend``.

Multi-structure files belong in a :class:`usif.dataset.Dataset`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional, Sequence, Union

from usif import backends as _backends
from usif.codec import jsondoc, record
from usif.errors import FormatError, MissingDependencyError, USIFError, ValidationError
from usif.fileio import atomic_write_bytes, atomic_write_text
from usif.model.properties import DEFAULT_SCHEMA, Schema
from usif.model.structure import Structure

__all__ = ["convert", "read", "read_all", "write", "write_all"]

PathLike = Union[str, "os.PathLike[str]"]
#: Upper bound on native files read into memory by :func:`read`.
MAX_FILE_SIZE = 2 * 1024**3


_RECORD_OPTIONS = frozenset({"compression", "level", "precision", "symmetry"})
_JSON_OPTIONS = frozenset({"indent"})


def _suffix(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".usif.json"):
        return ".json"
    return path.suffix.lower()


def _read_native(path: Path, schema: Schema) -> Optional[Structure]:
    suffix = _suffix(path)
    if suffix not in (".usif", ".json"):
        if suffix == ".usifc":
            raise ValidationError(f"{path} is a dataset; open it with usif.Dataset")
        return None
    size = path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise FormatError(f"{path} is larger than {MAX_FILE_SIZE} bytes")
    data = path.read_bytes()
    if suffix == ".json":
        return jsondoc.loads(data, schema=schema)
    if record.is_record(data):
        return record.decode(data, schema=schema)
    from usif.upgrade import format6

    if format6.is_format6(data):
        return format6.decode(data, schema=schema)
    raise FormatError(f"{path} is not a USIF record")


def _file_backends(name: Optional[str]) -> List[Any]:
    if name is not None:
        candidates = [_backends.get(name)]
    else:
        candidates = [b for b in _backends.backends() if _backends.available(b.name)]
    usable = [b for b in candidates if hasattr(b, "read") and hasattr(b, "write")]
    if not usable:
        raise MissingDependencyError(
            "matsimpy, ase or pymatgen",
            "reading and writing non-USIF file formats",
            "ase] or usif[pymatgen",
        )
    return usable


def read_all(
    source: PathLike,
    *,
    format: Optional[str] = None,
    backend: Optional[str] = None,
    schema: Schema = DEFAULT_SCHEMA,
) -> List[Structure]:
    """Every structure (frame) in a file."""
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(path)
    if backend is None and format is None:
        native = _read_native(path, schema)
        if native is not None:
            return [native]
    errors = []
    for candidate in _file_backends(backend):
        try:
            return list(candidate.read(path, format, schema=schema))
        except MissingDependencyError:
            raise
        except Exception as exc:  # try the next backend, report all failures
            errors.append(f"{candidate.name}: {exc}")
    raise FormatError(f"cannot read {path}: " + "; ".join(errors))


def read(
    source: Any,
    *,
    format: Optional[str] = None,
    backend: Optional[str] = None,
    schema: Schema = DEFAULT_SCHEMA,
) -> Structure:
    """Read a structure from a file, or convert a library object.

    ``source`` may be a path or a matsimpy/ASE/pymatgen (or plugin) object.
    A file holding several structures is an error; use :func:`read_all`.
    """
    if isinstance(source, Structure):
        return source
    if isinstance(source, (str, os.PathLike)):
        frames = read_all(source, format=format, backend=backend, schema=schema)
        if len(frames) != 1:
            raise FormatError(
                f"{source} holds {len(frames)} structures; use usif.read_all() or a Dataset"
            )
        return frames[0]
    return convert(source, schema=schema)


def write_all(
    structures: Sequence[Structure],
    path: PathLike,
    *,
    format: Optional[str] = None,
    backend: Optional[str] = None,
) -> None:
    """Write several structures to one file of a backend format (e.g. multi-frame XYZ)."""
    target = Path(path)
    if _suffix(target) in (".usif", ".json", ".usifc") and backend is None:
        raise ValidationError("native files hold one structure; use a Dataset for many")
    errors = []
    for candidate in _file_backends(backend):
        try:
            candidate.write(list(structures), target, format)
            return
        except MissingDependencyError:
            raise
        except Exception as exc:
            errors.append(f"{candidate.name}: {exc}")
    raise FormatError(f"cannot write {target}: " + "; ".join(errors))


def write(
    structure: Structure,
    path: PathLike,
    *,
    format: Optional[str] = None,
    backend: Optional[str] = None,
    **options: Any,
) -> None:
    """Write ``structure`` to ``path`` (atomically for native formats).

    ``.usif`` takes the :func:`usif.codec.encode` options (``compression``,
    ``level``, ``precision``, ``symmetry``); ``.json`` takes ``indent``.
    """
    if not isinstance(structure, Structure):
        raise ValidationError(f"expected a Structure, got {type(structure).__name__}")
    target = Path(path)
    suffix = _suffix(target)
    if backend is None and format is None and suffix in (".usif", ".json"):
        allowed = _RECORD_OPTIONS if suffix == ".usif" else _JSON_OPTIONS
        unknown = sorted(set(options) - allowed)
        if unknown:
            raise ValidationError(
                f"options {unknown} do not apply to {suffix} files (allowed: {sorted(allowed)})"
            )
        if suffix == ".usif":
            atomic_write_bytes(target, record.encode(structure, **options))
        else:
            atomic_write_text(target, jsondoc.dumps(structure, **options) + "\n")
        return
    if options:
        raise ValidationError(f"options {sorted(options)} apply only to .usif/.json files")
    write_all([structure], target, format=format, backend=backend)


def convert(obj: Any, to: Optional[str] = None, *, schema: Schema = DEFAULT_SCHEMA) -> Any:
    """Convert between :class:`Structure` and library objects.

    ``convert(atoms)`` returns a :class:`Structure`; ``convert(structure,
    "pymatgen")`` returns a pymatgen object; ``convert(atoms, "pymatgen")``
    goes through a :class:`Structure`.
    """
    if not isinstance(obj, Structure):
        source = _backends.for_object(obj)
        if source is None:
            raise ValidationError(
                f"no backend accepts {type(obj).__module__}.{type(obj).__qualname__}"
            )
        try:
            obj = source.to_structure(obj, schema=schema)
        except USIFError:
            raise
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            raise ValidationError(f"cannot convert {source.name} object: {exc}") from exc
    if to is None:
        return obj
    return _backends.get(to).from_structure(obj)
