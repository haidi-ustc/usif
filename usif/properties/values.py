"""Utilities for ergonomic, JSON-safe property value management."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Iterable, Optional, Sequence, Tuple

import numpy as np

_JSON_SCALAR_TYPES = (str, bool, int, float, type(None))


class PropertyValueKind(str, Enum):
    """High-level shape class for property values."""

    SCALAR = "scalar"
    VECTOR = "vector"
    TENSOR = "tensor"
    CUSTOM = "custom"


def normalize_json_value(value: Any) -> Any:
    """Return a JSON-compatible value while preserving numbers and nesting.

    Supported values are strings, booleans, integers, finite floats, ``None``,
    numpy scalars/arrays, tuples/lists, dictionaries with string keys, and
    objects exposing ``as_dict``.
    """
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (float, np.floating)):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"Property value must be finite, got {numeric!r}")
        return numeric
    if isinstance(value, np.ndarray):
        return normalize_json_value(value.tolist())
    if isinstance(value, tuple):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Custom property dictionaries require string keys, got {type(key).__name__}"
                )
            result[key] = normalize_json_value(item)
        return result
    if hasattr(value, "as_dict"):
        return normalize_json_value(value.as_dict())
    raise TypeError(f"Property value of type {type(value).__name__} is not JSON-compatible")


def as_scalar(name: str, value: Any) -> Any:
    """Validate and normalize a scalar property value."""
    normalized = normalize_json_value(value)
    if isinstance(normalized, list) or isinstance(normalized, dict):
        raise TypeError(f"Property '{name}' must be a scalar value")
    return normalized


def as_numeric_scalar(name: str, value: Any) -> float:
    """Return a finite float scalar."""
    normalized = as_scalar(name, value)
    if not isinstance(normalized, (int, float)) or isinstance(normalized, bool):
        raise TypeError(f"Property '{name}' must be numeric")
    return float(normalized)


def _flatten_numeric(value: Any) -> list[float]:
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        values: list[float] = []
        for item in value:
            values.extend(_flatten_numeric(item))
        return values
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"Numeric property values must be finite, got {numeric!r}")
        return [numeric]
    raise TypeError(f"Expected numeric value, got {type(value).__name__}")


def as_numeric_tuple(name: str, value: Any, *, length: Optional[int] = None) -> tuple[float, ...]:
    """Return a flat numeric tuple, optionally enforcing length."""
    values = tuple(_flatten_numeric(value))
    if length is not None and len(values) != length:
        raise ValueError(f"Property '{name}' must have {length} numeric values, got {len(values)}")
    return values


def as_vector(name: str, value: Any, *, length: int = 3) -> tuple[float, ...]:
    """Return a fixed-length numeric vector."""
    return as_numeric_tuple(name, value, length=length)


def as_tensor(name: str, value: Any, *, shape: Optional[tuple[int, ...]] = None) -> Any:
    """Return a JSON-compatible numeric tensor with optional shape validation."""
    normalized = normalize_json_value(value)
    if not isinstance(normalized, list):
        raise TypeError(f"Property '{name}' must be a tensor/list value")
    if shape is not None:
        actual = infer_shape(normalized)
        if actual != shape:
            raise ValueError(f"Property '{name}' must have shape {shape}, got {actual}")
    _validate_numeric_nested(name, normalized)
    return normalized


def infer_shape(value: Any) -> tuple[int, ...]:
    """Infer the rectangular shape of a nested list/tuple/array value."""
    if isinstance(value, np.ndarray):
        return tuple(int(dim) for dim in value.shape)
    if not isinstance(value, (list, tuple)):
        return ()
    length = len(value)
    if length == 0:
        return (0,)
    child_shapes = [infer_shape(item) for item in value]
    first = child_shapes[0]
    if any(shape != first for shape in child_shapes):
        raise ValueError("Tensor property values must be rectangular")
    return (length,) + first


def _validate_numeric_nested(name: str, value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _validate_numeric_nested(name, item)
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            raise ValueError(f"Property '{name}' contains non-finite number {value!r}")
        return
    raise TypeError(f"Property '{name}' tensor values must be numeric")


def stress_matrix_to_voigt(value: Any) -> tuple[float, float, float, float, float, float]:
    """Convert a 3x3 stress tensor matrix to USIF Voigt order.

    The order is ``(xx, yy, zz, yz, xz, xy)``.
    """
    matrix = as_tensor("stress", value, shape=(3, 3))
    return (
        float(matrix[0][0]),
        float(matrix[1][1]),
        float(matrix[2][2]),
        float(matrix[1][2]),
        float(matrix[0][2]),
        float(matrix[0][1]),
    )


def voigt_to_stress_matrix(value: Sequence[float]) -> list[list[float]]:
    """Convert USIF Voigt stress order to a symmetric 3x3 matrix."""
    xx, yy, zz, yz, xz, xy = as_numeric_tuple("stress", value, length=6)
    return [[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]]
