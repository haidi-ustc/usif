"""JSON-safe property value serializer helpers."""

from __future__ import annotations

from typing import Any

from usif.properties.values import PropertyValue, normalize_json_value


def serialize_json_value(value: Any) -> Any:
    """Normalize a property value to JSON-compatible Python objects."""
    return normalize_json_value(value)


def deserialize_json_value(value: Any) -> Any:
    """Return a JSON-compatible property value as loaded from JSON."""
    if isinstance(value, PropertyValue):
        return value.as_dict()
    return normalize_json_value(value)
