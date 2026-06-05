"""Property value validation helpers."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from usif.properties.definitions import PropertyDefinition
from usif.properties.serializers.common import (
    is_list_of_multi_dimensional_elements,
    is_multi_dimensional_element,
)


def validate_element(value: Any, prop_def: PropertyDefinition) -> bool:
    """Validate a single scalar/vector element against a property definition."""
    if prop_def.dimensions:
        if not isinstance(value, (tuple, list, np.ndarray)):
            return False
        try:
            if len(value) != prop_def.dimensions[0]:
                return False
            if not all(isinstance(x, (int, float)) for x in value):
                return False
        except (TypeError, ValueError):
            return False
    return True


def validate_value(
    value: Any, prop_def: PropertyDefinition, num_atoms: Optional[int] = None
) -> bool:
    """Validate a value against type, dimensions, and optional atom count."""
    if value is None:
        return True

    expected_type = prop_def.data_type
    if not isinstance(value, expected_type):
        if not (expected_type == float and isinstance(value, tuple) and prop_def.dimensions):
            if isinstance(value, np.ndarray) and expected_type in (float, int, tuple):
                pass
            elif (
                prop_def.is_per_atom
                and isinstance(value, (list, tuple))
                and len(value) > 0
                and num_atoms is not None
                and num_atoms > 1
            ):
                pass
            else:
                return False

    if prop_def.is_per_atom and prop_def.dimensions:
        if num_atoms is None:
            return validate_element(value, prop_def)
        if num_atoms == 1:
            if isinstance(value, (list, tuple, np.ndarray)) and len(value) == 1:
                return validate_element(value[0], prop_def)
            return validate_element(value, prop_def)

        if is_multi_dimensional_element(value):
            return validate_element(value, prop_def)
        if is_list_of_multi_dimensional_elements(value):
            return len(value) == num_atoms and all(validate_element(elem, prop_def) for elem in value)
        if isinstance(value, (list, tuple, np.ndarray)):
            return len(value) == num_atoms and all(validate_element(elem, prop_def) for elem in value)
        return validate_element(value, prop_def)

    return validate_element(value, prop_def)
