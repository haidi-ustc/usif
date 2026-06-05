"""Tensor property serializer for fixed-length numeric tensor records."""

from __future__ import annotations

from typing import Any, Tuple

from usif.properties.definitions import PropertyDefinition
from usif.properties.serializers.sequence import (
    deserialize_fixed_numeric_sequence,
    serialize_fixed_numeric_sequence,
)


def serialize_tensor(value: Any, prop_def: PropertyDefinition) -> bytes:
    """Serialize a fixed-size tensor record."""
    return serialize_fixed_numeric_sequence(value, prop_def, label="tensor")


def deserialize_tensor(data: bytes, offset: int, prop_def: PropertyDefinition) -> Tuple[Any, int]:
    """Deserialize a fixed-size tensor record."""
    return deserialize_fixed_numeric_sequence(data, offset, prop_def, label="tensor")

# The property dispatch layer stores fixed-dimensional numeric records through
# these internal names.
serialize_multi_dimensional = serialize_tensor
deserialize_multi_dimensional = deserialize_tensor

__all__ = [
    "serialize_tensor",
    "deserialize_tensor",
    "serialize_multi_dimensional",
    "deserialize_multi_dimensional",
]
