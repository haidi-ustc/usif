"""Scalar and string binary serializers."""

from __future__ import annotations

import struct
from typing import Any, Tuple

from usif.constants import BinaryFormat
from usif.exceptions import DecodingError, EncodingError
from usif.properties.definitions import PropertyDefinition
from usif.properties.serializers.common import LONG_COUNT_FLAG, TYPE_HANDLERS


def serialize_scalar_value(value: Any, prop_def: PropertyDefinition) -> bytes:
    """Serialize one scalar property value."""
    handler = TYPE_HANDLERS.get(prop_def.data_type)
    if not handler:
        raise EncodingError(f"Unsupported scalar type: {prop_def.data_type}")

    if prop_def.data_type == str:
        if not isinstance(value, str):
            raise EncodingError(f"Expected string, got {type(value).__name__}")
        return serialize_string(value)

    fmt = handler.get("format")
    if fmt:
        try:
            return struct.pack(fmt, value)
        except struct.error as e:
            raise EncodingError(f"Failed to pack value {value} with format {fmt}: {e}") from e
    raise EncodingError(f"Format not defined for {prop_def.data_type}")


def serialize_string(value: str) -> bytes:
    """Serialize a UTF-8 string using compact length encoding."""
    encoded = value.encode("utf-8")
    encoded_len = len(encoded)
    if encoded_len <= 255:
        return struct.pack(BinaryFormat.UINT8, encoded_len) + encoded
    return (
        struct.pack(BinaryFormat.UINT8, LONG_COUNT_FLAG)
        + struct.pack(BinaryFormat.UINT32, encoded_len)
        + encoded
    )


def deserialize_scalar_value(data: bytes, offset: int, prop_def: PropertyDefinition) -> Tuple[Any, int]:
    """Deserialize one scalar property value."""
    handler = TYPE_HANDLERS.get(prop_def.data_type)
    if not handler:
        raise DecodingError(f"Unsupported scalar data type: {prop_def.data_type}")

    if prop_def.data_type == str:
        return deserialize_string(data, offset)

    fmt = handler.get("format")
    if fmt:
        size = struct.calcsize(fmt)
        if offset + size > len(data):
            raise DecodingError(
                f"Insufficient data for scalar value: need {size} bytes at offset {offset}"
            )
        value = struct.unpack(fmt, data[offset : offset + size])[0]
        return value, offset + size
    raise DecodingError(f"Format not defined for {prop_def.data_type}")


def deserialize_string(data: bytes, offset: int) -> Tuple[str, int]:
    """Deserialize a UTF-8 string using compact length encoding."""
    if offset >= len(data):
        raise DecodingError(
            f"Insufficient data for string length: offset {offset} >= data length {len(data)}"
        )
    encoded_len = struct.unpack(BinaryFormat.UINT8, data[offset : offset + 1])[0]
    offset += 1

    if encoded_len == LONG_COUNT_FLAG:
        if offset + 4 > len(data):
            raise DecodingError(
                f"Insufficient data for long string length: need 4 bytes at offset {offset}"
            )
        encoded_len = struct.unpack(BinaryFormat.UINT32, data[offset : offset + 4])[0]
        offset += 4

    if encoded_len < 0 or encoded_len > 10000000:
        raise DecodingError(f"Invalid string length: {encoded_len}")
    if offset + encoded_len > len(data):
        raise DecodingError(
            f"Insufficient data for string content: need {encoded_len} bytes at offset {offset}"
        )
    value = data[offset : offset + encoded_len].decode("utf-8")
    return value, offset + encoded_len
