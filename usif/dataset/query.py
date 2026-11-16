"""Composable dataset queries compiled to parameterised SQL.

Examples::

    Q.formula("NaCl") & (Q.prop("energy") < -10)
    Q.elements("Fe", "O") & ~Q.elements("H") & Q.natoms(max=50)
    Q.group("/relaxed") | (Q.attr("source") == "mp")

Every user value is bound as an SQL parameter; property and attribute names
are parameters too, so no input is ever spliced into SQL text.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

from usif.elements import atomic_number
from usif.errors import ValidationError

__all__ = ["Q", "normalize_group"]

MAX_GROUP_DEPTH = 64


def normalize_group(path: str) -> str:
    """Canonical group path: ``"/"`` or ``"/a/b"`` (no trailing slash, no empty parts)."""
    if not isinstance(path, str):
        raise ValidationError("group paths must be strings")
    parts = [p for p in path.split("/") if p]
    for part in parts:
        if part in (".", "..") or any(ord(c) < 32 for c in part):
            raise ValidationError(f"invalid group path component {part!r}")
    if len(parts) > MAX_GROUP_DEPTH:
        raise ValidationError(f"group path deeper than {MAX_GROUP_DEPTH}")
    return "/" + "/".join(parts)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _json_path(key: str) -> str:
    if (
        not isinstance(key, str)
        or not key
        or any(c in key for c in '"\\')
        or any(ord(c) < 32 for c in key)
    ):
        raise ValidationError(f"invalid attribute key {key!r}")
    return f'$."{key}"'


def _scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return value
    raise ValidationError(f"query values must be numbers, strings or booleans, got {value!r}")


class Q:
    """A boolean condition on dataset entries (``e``) and their records (``r``)."""

    __slots__ = ("sql", "params")

    def __init__(self, sql: str, params: Sequence[Any] = ()) -> None:
        self.sql = sql
        self.params: Tuple[Any, ...] = tuple(params)

    # -- composition --------------------------------------------------------

    def __and__(self, other: "Q") -> "Q":
        return Q(f"({self.sql}) AND ({other.sql})", self.params + other.params)

    def __or__(self, other: "Q") -> "Q":
        return Q(f"({self.sql}) OR ({other.sql})", self.params + other.params)

    def __invert__(self) -> "Q":
        return Q(f"NOT ({self.sql})", self.params)

    def __repr__(self) -> str:
        return f"Q({self.sql!r}, {self.params!r})"

    # -- record conditions --------------------------------------------------

    @staticmethod
    def all() -> "Q":
        return Q("1")

    @staticmethod
    def formula(reduced_formula: str) -> "Q":
        """Reduced formula equality, e.g. ``"NaCl"`` (as :attr:`Structure.reduced_formula`)."""
        return Q("r.formula = ?", (str(reduced_formula),))

    @staticmethod
    def chemsys(system: str | Sequence[str]) -> "Q":
        """Exactly these elements, e.g. ``"Na-Cl"`` or ``["Cl", "Na"]``."""
        symbols = system.split("-") if isinstance(system, str) else list(system)
        for symbol in symbols:
            atomic_number(symbol)  # validates
        return Q("r.chemsys = ?", ("-".join(sorted(set(symbols))),))

    @staticmethod
    def elements(*symbols: str) -> "Q":
        """Contains every listed element (others allowed)."""
        if not symbols:
            raise ValidationError("elements() needs at least one symbol")
        parts = ["r.id IN (SELECT record_id FROM record_elements WHERE z = ?)"] * len(symbols)
        return Q(" AND ".join(parts), [atomic_number(s) for s in symbols])

    @staticmethod
    def natoms(min: Optional[int] = None, max: Optional[int] = None) -> "Q":
        conditions, params = [], []
        if min is not None:
            conditions.append("r.natoms >= ?")
            params.append(int(min))
        if max is not None:
            conditions.append("r.natoms <= ?")
            params.append(int(max))
        return Q(" AND ".join(conditions) or "1", params)

    @staticmethod
    def periodic(value: bool = True) -> "Q":
        return Q("r.periodic = ?", (int(bool(value)),))

    @staticmethod
    def geometry(geometry_hash: str) -> "Q":
        return Q("r.geometry_hash = ?", (bytes.fromhex(geometry_hash),))

    @staticmethod
    def record(record_hash: str) -> "Q":
        return Q("r.hash = ?", (bytes.fromhex(record_hash),))

    @staticmethod
    def has_prop(name: str) -> "Q":
        return Q(
            "r.id IN (SELECT record_id FROM record_values WHERE name = ?)",
            (name,),
        )

    @staticmethod
    def prop(name: str) -> "_Operand":
        """Numeric scalar structure property, e.g. ``Q.prop("energy") < 0``."""
        return _Operand(
            "r.id IN (SELECT record_id FROM record_values WHERE name = ? AND value {op} ?)",
            (name,),
            numeric=True,
        )

    # -- entry conditions ---------------------------------------------------

    @staticmethod
    def group(path: str, recursive: bool = True) -> "Q":
        path = normalize_group(path)
        if not recursive:
            return Q("e.grp = ?", (path,))
        if path == "/":
            return Q("1")
        return Q("(e.grp = ? OR e.grp LIKE ? ESCAPE '\\')", (path, _escape_like(path) + "/%"))

    @staticmethod
    def name(pattern: str) -> "Q":
        """Entry name matching a glob pattern (``*``, ``?``, ``[...]``)."""
        return Q("e.name GLOB ?", (str(pattern),))

    @staticmethod
    def has_attr(key: str) -> "Q":
        return Q("json_type(e.attrs, ?) IS NOT NULL", (_json_path(key),))

    @staticmethod
    def attr(key: str) -> "_Operand":
        """Top-level entry attribute, e.g. ``Q.attr("source") == "mp"``."""
        return _Operand("json_extract(e.attrs, ?) {op} ?", (_json_path(key),), numeric=False)


class _Operand:
    __slots__ = ("_template", "_params", "_numeric")

    def __init__(self, template: str, params: Tuple[Any, ...], numeric: bool) -> None:
        self._template = template
        self._params = params
        self._numeric = numeric

    def _compare(self, op: str, *values: Any) -> Q:
        values = tuple(_scalar(v) for v in values)
        if self._numeric and not all(isinstance(v, (int, float)) for v in values):
            raise ValidationError(f"property comparisons need numbers, got {values!r}")
        return Q(self._template.format(op=op), self._params + values)

    def __lt__(self, value: Any) -> Q:
        return self._compare("<", value)

    def __le__(self, value: Any) -> Q:
        return self._compare("<=", value)

    def __gt__(self, value: Any) -> Q:
        return self._compare(">", value)

    def __ge__(self, value: Any) -> Q:
        return self._compare(">=", value)

    def __eq__(self, value: Any) -> Q:  # type: ignore[override]
        return self._compare("=", value)

    def __ne__(self, value: Any) -> Q:  # type: ignore[override]
        return self._compare("!=", value)

    __hash__ = None  # type: ignore[assignment]

    def between(self, low: Any, high: Any) -> Q:
        """``low <= value <= high`` as one index range."""
        return self._compare("BETWEEN ? AND", low, high)
