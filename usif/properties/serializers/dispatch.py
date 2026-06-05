"""High-level binary property serialization dispatch."""

from __future__ import annotations

import struct
from typing import Any, Optional, Tuple

from usif.constants import BinaryFormat
from usif.exceptions import DecodingError, EncodingError
from usif.properties.definitions import PropertyDefinition
from usif.properties.serializers.common import (
    LONG_COUNT_FLAG,
    SINGLE_VALUE_FLAG,
    is_multi_dimensional_element,
    is_sequence,
)
from usif.properties.serializers.scalar import deserialize_scalar_value, serialize_scalar_value
from usif.properties.serializers.tensor import deserialize_multi_dimensional, serialize_multi_dimensional


def serialize_value(value: Any, prop_def: PropertyDefinition, num_atoms: Optional[int] = None) -> bytes:
    """Serialize a property value to binary format."""
    if value is None:
        return b""
    try:
        if prop_def.is_per_atom:
            return serialize_atom_property(value, prop_def, num_atoms)
        return serialize_structure_property(value, prop_def)
    except (struct.error, UnicodeEncodeError, ValueError, TypeError) as e:
        raise EncodingError(f"Failed to serialize property '{prop_def.name}': {e}") from e
    except Exception as e:
        raise EncodingError(f"Unexpected error serializing property '{prop_def.name}': {e}") from e


def serialize_atom_property(value: Any, prop_def: PropertyDefinition, num_atoms: Optional[int] = None) -> bytes:
    """Serialize a per-atom property with compact count encoding."""
    data = bytearray()
    is_multi_dim = is_multi_dimensional_element(value) and prop_def.dimensions
    is_seq = is_sequence(value) and not is_multi_dim

    if is_seq:
        actual_count = len(value)
        if actual_count == 0:
            raise EncodingError("Cannot serialize empty sequence for atomic property")
        if num_atoms is not None and actual_count != 1 and actual_count != num_atoms:
            raise EncodingError(
                f"Atomic property count mismatch: expected 1 or {num_atoms}, got {actual_count}"
            )
        if actual_count <= LONG_COUNT_FLAG - 1:
            data.extend(struct.pack(BinaryFormat.UINT8, actual_count))
        else:
            data.extend(struct.pack(BinaryFormat.UINT8, LONG_COUNT_FLAG))
            data.extend(struct.pack(BinaryFormat.UINT32, actual_count))
        for atom_value in value:
            data.extend(serialize_element(atom_value, prop_def))
    else:
        data.extend(struct.pack(BinaryFormat.UINT8, SINGLE_VALUE_FLAG))
        data.extend(serialize_element(value, prop_def))
    return bytes(data)


def serialize_structure_property(value: Any, prop_def: PropertyDefinition) -> bytes:
    """Serialize a structure-level property without atom count metadata."""
    return serialize_element(value, prop_def)


def serialize_element(value: Any, prop_def: PropertyDefinition) -> bytes:
    """Serialize one scalar or fixed-dimension element."""
    if prop_def.dimensions:
        return serialize_multi_dimensional(value, prop_def)
    return serialize_scalar_value(value, prop_def)


def deserialize_value(
    prop_def: PropertyDefinition, data: bytes, offset: int, num_atoms: Optional[int] = None
) -> Tuple[Any, int]:
    """Deserialize a property value from binary data."""
    if len(data) <= offset:
        return None, offset
    try:
        if prop_def.is_per_atom:
            return deserialize_atom_property(data, offset, prop_def, num_atoms)
        return deserialize_structure_property(data, offset, prop_def)
    except (struct.error, UnicodeDecodeError, ValueError, IndexError) as e:
        raise DecodingError(
            f"Failed to deserialize property '{prop_def.name}' at offset {offset}: {e}"
        ) from e
    except Exception as e:
        raise DecodingError(
            f"Unexpected error deserializing property '{prop_def.name}' at offset {offset}: {e}"
        ) from e


def deserialize_atom_property(
    data: bytes, offset: int, prop_def: PropertyDefinition, num_atoms: Optional[int] = None
) -> Tuple[Any, int]:
    """Deserialize a per-atom property with compact count encoding."""
    if offset >= len(data):
        raise DecodingError(f"Insufficient data: offset {offset} >= data length {len(data)}")

    count_flag = struct.unpack(BinaryFormat.UINT8, data[offset : offset + 1])[0]
    offset += 1

    if count_flag == SINGLE_VALUE_FLAG:
        value, offset = deserialize_element(data, offset, prop_def)
        return ([value] * num_atoms, offset) if num_atoms is not None and num_atoms > 1 else (value, offset)

    if count_flag == LONG_COUNT_FLAG:
        if offset + 4 > len(data):
            raise DecodingError(f"Insufficient data for long count: need 4 bytes at offset {offset}")
        count = struct.unpack(BinaryFormat.UINT32, data[offset : offset + 4])[0]
        offset += 4
    else:
        count = count_flag

    if num_atoms is not None and count != 1 and count != num_atoms:
        raise DecodingError(f"Atomic property count mismatch: expected 1 or {num_atoms}, got {count}")
    if count < 0 or count > 1000000:
        raise DecodingError(f"Invalid count value: {count}")

    values = []
    for _ in range(count):
        atom_value, offset = deserialize_element(data, offset, prop_def)
        values.append(atom_value)
    return values, offset


def deserialize_structure_property(data: bytes, offset: int, prop_def: PropertyDefinition) -> Tuple[Any, int]:
    """Deserialize a structure-level property."""
    return deserialize_element(data, offset, prop_def)


def deserialize_element(data: bytes, offset: int, prop_def: PropertyDefinition) -> Tuple[Any, int]:
    """Deserialize one scalar or fixed-dimension element."""
    if prop_def.dimensions:
        return deserialize_multi_dimensional(data, offset, prop_def)
    return deserialize_scalar_value(data, offset, prop_def)
