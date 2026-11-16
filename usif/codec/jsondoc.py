"""JSON document format ``usif.structure.json.v2``.

::

    {
      "schema": "usif.structure.json.v2",
      "numbers": [11, 17],
      "positions": [[0.0, 0.0, 0.0], [2.82, 2.82, 2.82]],
      "cell": {"matrix": [[...], [...], [...]], "pbc": [true, true, true]},   # or null
      "arrays": {"force": {"dtype": "<f8", "unit": "eV/Å", "value": [[...], ...]}},
      "properties": {"energy": {"dtype": "<f8", "unit": "eV", "value": -10.5}}
    }

Floats are written with full precision (``repr``), so the document round
trips exactly. ``dtype`` is a NumPy dtype string or ``"json"``.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import numpy as np

from usif.errors import FormatError, ValidationError
from usif.model.properties import DEFAULT_SCHEMA, JSON, NUMERIC_DTYPES, PropertyMap, Schema
from usif.model.structure import Structure

__all__ = ["SCHEMA_ID", "dumps", "from_document", "loads", "to_document"]

SCHEMA_ID = "usif.structure.json.v2"
#: Upper bound on the JSON text accepted by :func:`loads`.
DEFAULT_MAX_SIZE = 512 * 1024**2


def _columns_to_json(columns: PropertyMap) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name in sorted(columns):
        dtype = columns.dtype(name)
        raw = columns.raw(name)
        out[name] = {
            "dtype": dtype,
            "unit": columns.unit(name),
            "value": raw if dtype == JSON else raw.tolist(),
        }
    return out


def _columns_from_json(data: Any, target: PropertyMap, where: str) -> None:
    if not isinstance(data, dict):
        raise FormatError(f"{where} must be an object")
    for name, entry in data.items():
        if not isinstance(entry, dict) or "value" not in entry:
            raise FormatError(f"{where}.{name} must be an object with a 'value'")
        dtype = entry.get("dtype", JSON)
        unit = entry.get("unit", "")
        if not isinstance(unit, str):
            raise FormatError(f"{where}.{name}.unit must be a string")
        value = entry["value"]
        if dtype != JSON:
            if dtype not in NUMERIC_DTYPES:
                raise FormatError(f"{where}.{name} has unsupported dtype {dtype!r}")
            try:
                value = np.asarray(value, dtype=dtype)
            except (TypeError, ValueError) as exc:
                raise FormatError(f"{where}.{name} does not match dtype {dtype}: {exc}") from exc
        try:
            target.set(name, value, unit=unit)
        except ValidationError as exc:
            raise FormatError(f"{where}.{name} is invalid: {exc}") from exc


def to_document(structure: Structure) -> Dict[str, Any]:
    cell = structure.cell
    return {
        "schema": SCHEMA_ID,
        "numbers": structure.numbers.tolist(),
        "positions": structure.positions.tolist(),
        "cell": None if cell is None else {"matrix": cell.matrix.tolist(), "pbc": list(cell.pbc)},
        "arrays": _columns_to_json(structure.arrays),
        "properties": _columns_to_json(structure.properties),
    }


def from_document(document: Any, *, schema: Schema = DEFAULT_SCHEMA) -> Structure:
    if not isinstance(document, dict):
        raise FormatError("a USIF JSON document must be an object")
    if document.get("schema") != SCHEMA_ID:
        raise FormatError(
            f"unsupported JSON schema {document.get('schema')!r}; expected {SCHEMA_ID!r}"
        )
    cell = document.get("cell")
    try:
        if cell is not None:
            if not isinstance(cell, dict):
                raise FormatError("cell must be an object or null")
            structure = Structure(
                document["numbers"],
                document["positions"],
                cell.get("matrix"),
                pbc=cell.get("pbc", True),
                schema=schema,
            )
        else:
            structure = Structure(document["numbers"], document["positions"], schema=schema)
    except KeyError as exc:
        raise FormatError(f"JSON document is missing {exc}") from exc
    except ValidationError as exc:
        raise FormatError(f"JSON document holds an invalid structure: {exc}") from exc
    _columns_from_json(document.get("arrays", {}), structure.arrays, "arrays")
    _columns_from_json(document.get("properties", {}), structure.properties, "properties")
    return structure


def dumps(structure: Structure, *, indent: int | None = 2) -> str:
    return json.dumps(to_document(structure), indent=indent, ensure_ascii=False, allow_nan=False)


def loads(text: str | bytes, *, schema: Schema = DEFAULT_SCHEMA) -> Structure:
    if len(text) > DEFAULT_MAX_SIZE:
        raise FormatError(f"JSON document exceeds {DEFAULT_MAX_SIZE} bytes")
    try:
        document = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise FormatError(f"invalid JSON: {exc}") from exc
    return from_document(document, schema=schema)
