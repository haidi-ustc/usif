"""Serialized-size estimation helpers."""

from __future__ import annotations

from typing import Any, Optional

from usif.properties.definitions import PropertyDefinition
from usif.properties.serializers.common import (
    LONG_COUNT_FLAG,
    TYPE_HANDLERS,
    get_atom_count,
    is_multi_dimensional_element,
)


def get_expected_size(
    prop_def: PropertyDefinition, value: Any = None, num_atoms: Optional[int] = None
) -> int:
    """Estimate the serialized size in bytes for a property value."""
    if value is None:
        return 0

    handler = TYPE_HANDLERS.get(prop_def.data_type)
    if not handler:
        return 0

    if not prop_def.dimensions:
        if prop_def.data_type == str:
            if not isinstance(value, str):
                return 0
            size_func = handler.get("size")
            return size_func(value) if callable(size_func) else size_func
        size = handler.get("size")
        return size(value) if callable(size) else size

    if prop_def.is_per_atom:
        actual_count = 1 if is_multi_dimensional_element(value) and prop_def.dimensions else get_atom_count(value, num_atoms)
        count_size = 1 if actual_count <= LONG_COUNT_FLAG - 1 else 5
        if actual_count is None or actual_count <= 0:
            return count_size
        dim = prop_def.dimensions[0]
        element_size_val = handler.get("size")
        element_size = element_size_val(dim) if callable(element_size_val) else element_size_val * dim
        return count_size + (actual_count * element_size)

    dim = prop_def.dimensions[0]
    size_val = handler.get("size")
    return size_val(dim) if callable(size_val) else size_val * dim
