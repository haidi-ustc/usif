"""Vector/tensor binary serializers for fixed-size numeric dimensions."""

from __future__ import annotations

import struct
from typing import Any, Tuple

from usif.constants import BinaryFormat
from usif.exceptions import DecodingError, EncodingError
from usif.properties.definitions import PropertyDefinition
from usif.properties.serializers.common import TYPE_HANDLERS, is_sequence


def serialize_multi_dimensional(value: Any, prop_def: PropertyDefinition) -> bytes:
    """Serialize a fixed-size numeric vector or tensor row."""
    dim = prop_def.dimensions[0]
    if not is_sequence(value):
        raise EncodingError(
            f"Expected sequence for multi-dimensional property, got {type(value).__name__}"
        )
    if len(value) != dim:
        raise EncodingError(f"Dimension mismatch: expected {dim} elements, got {len(value)}")
    if not all(isinstance(x, (int, float)) for x in value):
        raise EncodingError("All elements must be numeric (int or float), got mixed types")

    handler = TYPE_HANDLERS.get(prop_def.data_type)
    if not handler:
        raise EncodingError(f"Unsupported multi-dimensional type: {prop_def.data_type}")
    fmt = handler.get("format")
    if fmt is None:
        raise EncodingError(f"Format not defined for {prop_def.data_type}")

    if prop_def.data_type == bool:
        bool_bytes = [1 if x else 0 for x in value]
        return struct.pack(BinaryFormat.array(BinaryFormat.UINT8, dim), *bool_bytes)
    return struct.pack(BinaryFormat.array(fmt, dim), *value)


def deserialize_multi_dimensional(
    data: bytes, offset: int, prop_def: PropertyDefinition
) -> Tuple[Any, int]:
    """Deserialize a fixed-size numeric vector or tensor row."""
    dim = prop_def.dimensions[0]
    handler = TYPE_HANDLERS.get(prop_def.data_type)
    if not handler:
        raise DecodingError(f"Unsupported multi-dimensional type: {prop_def.data_type}")
    fmt = handler.get("format")
    if fmt is None:
        raise DecodingError(f"Format not defined for {prop_def.data_type}")

    element_size = handler.get("size")
    size = element_size(dim) if callable(element_size) else element_size * dim
    if offset + size > len(data):
        raise DecodingError(
            f"Insufficient data for multi-dimensional value: need {size} bytes at offset {offset}"
        )

    if prop_def.data_type == bool:
        if offset + dim > len(data):
            raise DecodingError(
                f"Insufficient data for multi-dimensional value: need {dim} bytes at offset {offset}"
            )
        bool_values = struct.unpack(
            BinaryFormat.array(BinaryFormat.UINT8, dim), data[offset : offset + dim]
        )
        return tuple(bool(x) for x in bool_values), offset + dim

    values = struct.unpack(BinaryFormat.array(fmt, dim), data[offset : offset + size])
    return tuple(values), offset + size
