#!/usr/bin/env python3
"""Public binary property serializer facade.

The implementation is split across ``usif.properties.serializers`` so scalar,
vector/tensor, JSON-safe value, validation, and size-estimation concerns can be
maintained independently.  ``PropertySerializer`` remains the stable public API.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from usif.properties.definitions import PropertyDefinition
from usif.properties.serializers.common import (
    LONG_COUNT_FLAG,
    SINGLE_VALUE_FLAG,
    TYPE_HANDLERS,
    get_atom_count,
    get_string_size,
    is_list_of_multi_dimensional_elements,
    is_multi_dimensional_element,
    is_sequence,
)
from usif.properties.serializers.dispatch import (
    deserialize_atom_property,
    deserialize_element,
    deserialize_structure_property,
    deserialize_value,
    serialize_atom_property,
    serialize_element,
    serialize_structure_property,
    serialize_value,
)
from usif.properties.serializers.scalar import (
    deserialize_scalar_value,
    deserialize_string,
    serialize_scalar_value,
    serialize_string,
)
from usif.properties.serializers.size import get_expected_size
from usif.properties.serializers.tensor import deserialize_multi_dimensional, serialize_multi_dimensional
from usif.properties.serializers.validation import validate_element, validate_value


class PropertySerializer:
    """Serialize and deserialize property values.

    This class is intentionally a thin facade.  New serializer logic belongs in
    the focused modules under :mod:`usif.properties.serializers`.
    """

    SINGLE_VALUE_FLAG = SINGLE_VALUE_FLAG
    LONG_COUNT_FLAG = LONG_COUNT_FLAG
    TYPE_HANDLERS = TYPE_HANDLERS

    @staticmethod
    def serialize_value(
        value: Any, prop_def: PropertyDefinition, num_atoms: Optional[int] = None
    ) -> bytes:
        """Serialize a property value to USIF binary bytes."""
        return serialize_value(value, prop_def, num_atoms)

    @staticmethod
    def deserialize_value(
        prop_def: PropertyDefinition,
        data: bytes,
        offset: int,
        num_atoms: Optional[int] = None,
    ) -> Tuple[Any, int]:
        """Deserialize a property value from USIF binary bytes."""
        return deserialize_value(prop_def, data, offset, num_atoms)

    @staticmethod
    def validate_value(
        value: Any, prop_def: PropertyDefinition, num_atoms: Optional[int] = None
    ) -> bool:
        """Return True when a property value matches its definition."""
        return validate_value(value, prop_def, num_atoms)

    @staticmethod
    def get_expected_size(
        prop_def: PropertyDefinition, value: Any = None, num_atoms: Optional[int] = None
    ) -> int:
        """Estimate the serialized size in bytes for a property value."""
        return get_expected_size(prop_def, value, num_atoms)

    # Internal delegates kept so implementation-level tests can target the
    # facade while the real logic remains in focused modules.
    _get_string_size = staticmethod(get_string_size)
    _is_sequence = staticmethod(is_sequence)
    _get_atom_count = staticmethod(get_atom_count)
    _serialize_atom_property = staticmethod(serialize_atom_property)
    _serialize_structure_property = staticmethod(serialize_structure_property)
    _serialize_element = staticmethod(serialize_element)
    _serialize_multi_dimensional = staticmethod(serialize_multi_dimensional)
    _serialize_scalar_value = staticmethod(serialize_scalar_value)
    _serialize_string = staticmethod(serialize_string)
    _deserialize_atom_property = staticmethod(deserialize_atom_property)
    _deserialize_structure_property = staticmethod(deserialize_structure_property)
    _deserialize_multi_dimensional = staticmethod(deserialize_multi_dimensional)
    _deserialize_element = staticmethod(deserialize_element)
    _deserialize_scalar_value = staticmethod(deserialize_scalar_value)
    _deserialize_string = staticmethod(deserialize_string)
    _is_multi_dimensional_element = staticmethod(is_multi_dimensional_element)
    _is_list_of_multi_dimensional_elements = staticmethod(is_list_of_multi_dimensional_elements)
    _validate_element = staticmethod(validate_element)
