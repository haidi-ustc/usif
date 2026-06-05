"""JSON persistence helpers for USIF structures.

The JSON service is intentionally separate from the binary ``.usif`` codec.  It
writes a human-readable, JSON-compatible representation of the pure
``USIFStructure`` model and restores it through ``USIFStructure.from_dict``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Union

import numpy as np

from usif.exceptions import StorageError
from usif.structures import USIFStructure

JSON_SCHEMA = "usif.structure.json.v1"


def _to_json_compatible(value: Any) -> Any:
    """Convert supported Python/scientific values into JSON-compatible data."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (float, np.floating)):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise StorageError(f"JSON does not support non-finite float value: {numeric!r}")
        return numeric
    if isinstance(value, np.ndarray):
        return _to_json_compatible(value.tolist())
    if isinstance(value, tuple):
        return [_to_json_compatible(item) for item in value]
    if isinstance(value, list):
        return [_to_json_compatible(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise StorageError(
                    f"JSON structure dictionaries require string keys, got {type(key).__name__}"
                )
            result[key] = _to_json_compatible(item)
        return result
    if hasattr(value, "as_dict"):
        return _to_json_compatible(value.as_dict())
    raise StorageError(f"Value of type {type(value).__name__} is not JSON serializable")


def structure_to_json_dict(structure: USIFStructure) -> dict[str, Any]:
    """Return a JSON-compatible dictionary for a ``USIFStructure``."""
    data = _to_json_compatible(structure.as_dict())
    if not isinstance(data, dict):  # defensive; as_dict always returns dict
        raise StorageError("USIFStructure.as_dict() did not return a dictionary")
    data.setdefault("@schema", JSON_SCHEMA)
    return data


def structure_from_json_dict(data: dict[str, Any]) -> USIFStructure:
    """Restore a ``USIFStructure`` from a JSON dictionary."""
    if not isinstance(data, dict):
        raise StorageError("USIF JSON payload must be an object")
    schema = data.get("@schema")
    if schema is not None and schema != JSON_SCHEMA:
        raise StorageError(f"Unsupported USIF JSON schema: {schema!r}")
    return USIFStructure.from_dict(data)


def save_structure_json(
    structure: USIFStructure,
    filename: Union[str, Path],
    *,
    indent: int = 2,
    sort_keys: bool = True,
) -> None:
    """Save a ``USIFStructure`` as human-readable JSON."""
    filename = Path(filename)
    try:
        with filename.open("w", encoding="utf-8") as handle:
            json.dump(
                structure_to_json_dict(structure),
                handle,
                indent=indent,
                sort_keys=sort_keys,
                ensure_ascii=False,
                allow_nan=False,
            )
            handle.write("\n")
    except OSError as e:
        raise StorageError(f"Failed to save JSON structure to {filename}: {e}") from e


def load_structure_json(filename: Union[str, Path]) -> USIFStructure:
    """Load a ``USIFStructure`` from JSON."""
    filename = Path(filename)
    try:
        with filename.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as e:
        raise StorageError(f"Failed to load JSON structure from {filename}: {e}") from e
    return structure_from_json_dict(data)


__all__ = [
    "JSON_SCHEMA",
    "load_structure_json",
    "save_structure_json",
    "structure_from_json_dict",
    "structure_to_json_dict",
]
