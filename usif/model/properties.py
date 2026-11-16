"""Typed property columns with units.

A *property* is a named value with a unit:

* per-atom properties are arrays whose leading dimension is the atom count;
* structure properties are scalars, arrays or JSON values.

A :class:`Schema` holds :class:`PropertySpec` entries that fix the dtype,
per-entry shape and default unit of well-known names (``energy``, ``force``,
...). Names without a spec are accepted with an inferred dtype. Values are
validated and normalised on assignment, never converted between units.
"""

from __future__ import annotations

import copy as _copy
import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, Mapping, MutableMapping, Optional, Tuple

import numpy as np

from usif.errors import ValidationError
from usif.units import normalize_unit

__all__ = [
    "DEFAULT_SCHEMA",
    "JSON",
    "NUMERIC_DTYPES",
    "PropertyMap",
    "PropertySpec",
    "Schema",
    "normalize_json",
    "stress_to_voigt",
    "voigt_to_tensor",
]

#: dtype marker for arbitrary JSON values.
JSON = "json"

#: Numeric dtypes a property may use (the record format's whitelist).
NUMERIC_DTYPES = frozenset(
    np.dtype(name).str
    for name in (
        "bool",
        "int8",
        "int16",
        "int32",
        "int64",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "float32",
        "float64",
    )
)

MAX_NAME_BYTES = 255

Shape = Optional[Tuple[int, ...]]


# -- helpers ------------------------------------------------------------------


def stress_to_voigt(stress: Any) -> np.ndarray:
    """3x3 tensor or 6-vector -> Voigt order (xx, yy, zz, yz, xz, xy)."""
    array = np.asarray(stress, dtype=np.float64)
    if array.shape == (3, 3):
        return np.array(
            [array[0, 0], array[1, 1], array[2, 2], array[1, 2], array[0, 2], array[0, 1]]
        )
    if array.shape == (6,):
        return array
    raise ValidationError(f"stress must be a 3x3 tensor or a 6-vector, got shape {array.shape}")


def _magmom(value: Any) -> Any:
    """Per-atom magnetic moments: shape (N,) collinear or (N, 3) non-collinear."""
    shape = np.shape(value)
    if len(shape) == 1 or (len(shape) == 2 and shape[1] == 3):
        return value
    raise ValidationError(f"magmom must have shape (N,) or (N, 3), got {shape}")


def _multiplicity(value: Any) -> Any:
    """Spin multiplicity 2S+1 is a positive integer."""
    if np.any(np.asarray(value) < 1):
        raise ValidationError(f"spin_multiplicity must be >= 1, got {value!r}")
    return value


def voigt_to_tensor(voigt: Any) -> np.ndarray:
    xx, yy, zz, yz, xz, xy = np.asarray(voigt, dtype=np.float64)
    return np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])


def normalize_json(value: Any, *, path: str = "value") -> Any:
    """Return ``value`` as plain JSON types (dict/list/str/int/float/bool/None).

    NumPy scalars and arrays and tuples are converted; non-finite floats,
    non-string keys and other objects are rejected.
    """
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError(f"{path} contains a non-finite number")
        return float(value)
    if isinstance(value, np.ndarray):
        return normalize_json(value.tolist(), path=path)
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError(f"{path} has a non-string key {key!r}")
            result[key] = normalize_json(item, path=f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [normalize_json(item, path=f"{path}[{i}]") for i, item in enumerate(value)]
    raise ValidationError(f"{path} of type {type(value).__name__} is not JSON-compatible")


def _check_name(name: Any) -> str:
    if not isinstance(name, str) or not name:
        raise ValidationError("property names must be non-empty strings")
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        raise ValidationError(f"property name {name[:32]!r}... exceeds {MAX_NAME_BYTES} bytes")
    if any(ord(ch) < 32 for ch in name):
        raise ValidationError(f"property name {name!r} contains control characters")
    return name


# -- specs and schema ---------------------------------------------------------


@dataclass(frozen=True)
class PropertySpec:
    """Dtype, per-entry shape and default unit of a named property.

    ``shape`` excludes the atom axis of per-atom properties; ``None`` accepts
    any shape. ``coerce`` optionally maps accepted input forms to the
    canonical one (e.g. a 3x3 stress tensor to Voigt order).
    """

    name: str
    dtype: str
    shape: Shape = ()
    unit: str = ""
    description: str = ""
    coerce: Optional[Callable[[Any], Any]] = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        _check_name(self.name)
        if self.dtype != JSON:
            object.__setattr__(self, "dtype", np.dtype(self.dtype).str)
            if self.dtype not in NUMERIC_DTYPES:
                raise ValidationError(f"unsupported dtype {self.dtype} for {self.name!r}")
        object.__setattr__(self, "unit", normalize_unit(self.unit))


class Schema:
    """Registry of property specs, separately for per-atom and structure scope."""

    def __init__(
        self,
        atom_specs: Mapping[str, PropertySpec] | None = None,
        structure_specs: Mapping[str, PropertySpec] | None = None,
    ) -> None:
        self._atom: Dict[str, PropertySpec] = dict(atom_specs or {})
        self._structure: Dict[str, PropertySpec] = dict(structure_specs or {})

    def atom(self, name: str) -> Optional[PropertySpec]:
        return self._atom.get(name)

    def structure(self, name: str) -> Optional[PropertySpec]:
        return self._structure.get(name)

    def register(self, spec: PropertySpec, *, per_atom: bool) -> None:
        (self._atom if per_atom else self._structure)[spec.name] = spec

    def atom_specs(self) -> Dict[str, PropertySpec]:
        return dict(self._atom)

    def structure_specs(self) -> Dict[str, PropertySpec]:
        return dict(self._structure)

    def copy(self) -> "Schema":
        return Schema(self._atom, self._structure)

    @classmethod
    def default(cls) -> "Schema":
        f8 = "float64"
        atom = [
            PropertySpec("force", f8, (3,), "eV/Å", "Force on the atom"),
            PropertySpec("charge", f8, (), "e", "Atomic (partial) charge"),
            PropertySpec(
                "magmom", f8, None, "μB", "Magnetic moment: scalar or 3-vector", coerce=_magmom
            ),
            PropertySpec("velocity", f8, (3,), "Å/fs", "Atomic velocity"),
        ]
        structure = [
            PropertySpec("energy", f8, (), "eV", "Total (potential) energy of the structure"),
            PropertySpec("free_energy", f8, (), "eV", "Free energy (e.g. Mermin, with smearing)"),
            PropertySpec(
                "stress",
                f8,
                (6,),
                "GPa",
                "Cauchy stress, Voigt order (xx, yy, zz, yz, xz, xy); positive is tensile, "
                "so pressure = -(xx + yy + zz) / 3 (the ASE sign; VASP prints the opposite)",
                coerce=stress_to_voigt,
            ),
            PropertySpec("pressure", f8, (), "GPa", "Pressure; positive is compressive"),
            PropertySpec("dipole", f8, (3,), "e·Å", "Electric dipole moment"),
            PropertySpec("temperature", f8, (), "K", "Temperature"),
            PropertySpec("charge", f8, (), "e", "Total charge"),
            PropertySpec(
                "spin_multiplicity", "int64", (), "", "Spin multiplicity 2S+1", coerce=_multiplicity
            ),
        ]
        return cls({s.name: s for s in atom}, {s.name: s for s in structure})


DEFAULT_SCHEMA = Schema.default()


# -- value normalisation ------------------------------------------------------


def _normalize(
    name: str, value: Any, spec: Optional[PropertySpec], length: Optional[int]
) -> Tuple[Any, str]:
    """Return ``(stored_value, dtype)``; numeric values become read-only arrays."""
    if spec is not None and spec.coerce is not None:
        value = spec.coerce(value)

    if spec is not None and spec.dtype == JSON:
        return _normalize_json_value(name, value, length), JSON

    if spec is None:
        array = None
        if not isinstance(value, (str, Mapping)):
            try:
                candidate = np.asarray(value)
            except (ValueError, TypeError):
                candidate = None
            if candidate is not None and candidate.dtype.kind in "biuf":
                array = candidate
        if array is None:
            return _normalize_json_value(name, value, length), JSON
        if array.dtype.str not in NUMERIC_DTYPES:  # e.g. float16, longdouble
            array = array.astype(np.float64 if array.dtype.kind == "f" else np.int64)
    else:
        try:
            raw = np.asarray(value)
            if raw.dtype.kind not in "biuf":
                raise TypeError(f"dtype {raw.dtype}")
            array = raw.astype(spec.dtype, casting="same_kind")
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{name!r} must be numeric ({spec.dtype}): {exc}") from exc
        # same_kind casting allows int64 -> int8 or uint64 -> int64, which wrap around.
        if array.dtype.kind in "iu" and raw.dtype.kind in "iu" and not _same_integers(raw, array):
            raise ValidationError(f"{name!r} has values out of range for {spec.dtype}")

    if array.dtype.kind == "f" and not np.all(np.isfinite(array)):
        raise ValidationError(f"{name!r} contains non-finite values")

    entry_shape = array.shape
    if length is not None:
        if array.ndim == 0 or array.shape[0] != length:
            raise ValidationError(
                f"per-atom property {name!r} needs leading dimension {length}, "
                f"got shape {array.shape}"
            )
        entry_shape = array.shape[1:]
    if spec is not None and spec.shape is not None and tuple(entry_shape) != spec.shape:
        raise ValidationError(f"{name!r} must have entry shape {spec.shape}, got {entry_shape}")

    array = np.array(array, copy=True, order="C")
    array.flags.writeable = False
    return array, array.dtype.str


def _same_integers(a: np.ndarray, b: np.ndarray) -> bool:
    """Whether integer array ``b`` (a cast of ``a``) kept every value of ``a``.

    An integer cast is lossless exactly when casting back restores the input.
    """
    return bool(np.array_equal(b.astype(a.dtype), a)) and bool(np.all((a < 0) == (b < 0)))


def _normalize_json_value(name: str, value: Any, length: Optional[int]) -> Any:
    result = normalize_json(value, path=name)
    if length is not None and (not isinstance(result, list) or len(result) != length):
        raise ValidationError(f"per-atom property {name!r} needs {length} entries")
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as exc:  # pragma: no cover - normalize_json guards this
        raise ValidationError(f"{name!r} is not JSON-serialisable: {exc}") from exc
    return result


# -- container ----------------------------------------------------------------


class PropertyMap(MutableMapping[str, Any]):
    """Named, unit-carrying property values of one scope.

    ``map[name]`` returns Python scalars for 0-d numeric values, read-only
    arrays for other numeric values and copies of JSON values.
    """

    __slots__ = ("_lookup", "_length", "_values", "_units", "_dtypes")

    def __init__(
        self,
        lookup: Callable[[str], Optional[PropertySpec]],
        length: Optional[int] = None,
    ) -> None:
        self._lookup = lookup
        self._length = length
        self._values: Dict[str, Any] = {}
        self._units: Dict[str, str] = {}
        self._dtypes: Dict[str, str] = {}

    # -- writing ------------------------------------------------------------

    def set(self, name: str, value: Any, unit: Optional[str] = None) -> None:
        """Set ``name``; ``unit`` defaults to the schema unit (or no unit)."""
        _check_name(name)
        spec = self._lookup(name)
        stored, dtype = _normalize(name, value, spec, self._length)
        self._values[name] = stored
        self._dtypes[name] = dtype
        if unit is None:
            unit = spec.unit if spec is not None else ""
        self._units[name] = normalize_unit(unit)

    def set_unit(self, name: str, unit: Optional[str]) -> None:
        if name not in self._values:
            raise KeyError(name)
        self._units[name] = normalize_unit(unit)

    def update_from(self, values: Mapping[str, Any] | None) -> None:
        for name, value in (values or {}).items():
            self.set(name, value)

    # -- reading ------------------------------------------------------------

    def unit(self, name: str) -> str:
        if name not in self._values:
            raise KeyError(name)
        return self._units[name]

    def units(self) -> Dict[str, str]:
        return dict(self._units)

    def dtype(self, name: str) -> str:
        """NumPy dtype string (``'<f8'``) or :data:`JSON`."""
        if name not in self._values:
            raise KeyError(name)
        return self._dtypes[name]

    def raw(self, name: str) -> Any:
        """Stored value: a read-only array for numeric values, JSON data otherwise."""
        return self._values[name]

    @property
    def length(self) -> Optional[int]:
        return self._length

    # -- MutableMapping -----------------------------------------------------

    def __getitem__(self, name: str) -> Any:
        value = self._values[name]
        if isinstance(value, np.ndarray):
            return value.item() if value.ndim == 0 else value
        return _copy.deepcopy(value)

    def __setitem__(self, name: str, value: Any) -> None:
        self.set(name, value)

    def __delitem__(self, name: str) -> None:
        del self._values[name]
        del self._units[name]
        del self._dtypes[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PropertyMap):
            return NotImplemented
        if self._values.keys() != other._values.keys():
            return False
        if self._units != other._units or self._dtypes != other._dtypes:
            return False
        for name, value in self._values.items():
            theirs = other._values[name]
            if isinstance(value, np.ndarray):
                if not np.array_equal(value, theirs):
                    return False
            elif value != theirs:
                return False
        return True

    __hash__ = None  # type: ignore[assignment]

    def allclose(self, other: "PropertyMap", atol: float) -> bool:
        if self._values.keys() != other._values.keys() or self._units != other._units:
            return False
        for name, value in self._values.items():
            theirs = other._values[name]
            if isinstance(value, np.ndarray) and isinstance(theirs, np.ndarray):
                if value.shape != theirs.shape:
                    return False
                if value.dtype.kind == "f" or theirs.dtype.kind == "f":
                    if not np.allclose(value, theirs, atol=atol, rtol=0):
                        return False
                elif not np.array_equal(value, theirs):
                    return False
            elif value != theirs:
                return False
        return True

    def copy(
        self, lookup: Optional[Callable[[str], Optional[PropertySpec]]] = None
    ) -> "PropertyMap":
        clone = PropertyMap(lookup or self._lookup, self._length)
        clone._values = {
            k: (v if isinstance(v, np.ndarray) else _copy.deepcopy(v))
            for k, v in self._values.items()
        }
        clone._units = dict(self._units)
        clone._dtypes = dict(self._dtypes)
        return clone

    def subset(self, index: np.ndarray) -> "PropertyMap":
        """Per-atom map restricted/reordered to ``index`` (an integer array)."""
        if self._length is None:
            raise TypeError("subset() applies to per-atom maps only")
        clone = PropertyMap(self._lookup, len(index))
        for name, value in self._values.items():
            if isinstance(value, np.ndarray):
                picked = value[index]
                picked.flags.writeable = False
                clone._values[name] = picked
            else:
                clone._values[name] = [_copy.deepcopy(value[i]) for i in index]
            clone._units[name] = self._units[name]
            clone._dtypes[name] = self._dtypes[name]
        return clone

    def __repr__(self) -> str:
        items = ", ".join(f"{k}[{self._units[k]}]" if self._units[k] else k for k in self._values)
        return f"PropertyMap({items})"
