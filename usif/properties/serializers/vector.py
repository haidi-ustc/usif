"""Vector property serializer for fixed-length numeric vectors."""

from __future__ import annotations

from typing import Any, Tuple

from usif.properties.definitions import PropertyDefinition
from usif.properties.serializers.sequence import (
    deserialize_fixed_numeric_sequence,
    serialize_fixed_numeric_sequence,
)


def serialize_vector(value: Any, prop_def: PropertyDefinition) -> bytes:
    """Serialize a fixed-length vector property."""
    return serialize_fixed_numeric_sequence(value, prop_def, label="vector")


def deserialize_vector(data: bytes, offset: int, prop_def: PropertyDefinition) -> Tuple[Any, int]:
    """Deserialize a fixed-length vector property."""
    return deserialize_fixed_numeric_sequence(data, offset, prop_def, label="vector")


__all__ = ["serialize_vector", "deserialize_vector"]
