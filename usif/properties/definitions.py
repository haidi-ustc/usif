#!/usr/bin/env python3
"""
USIF Property Definition Module

This module provides the PropertyDefinition class for defining type-safe properties
with validation, units, and constraints. Properties can be atomic (per-atom) or
structure-level, and can be scalar or multi-dimensional.

Main Class:
    PropertyDefinition: Define property types with validation and constraints

Features:
    - Type safety with generic type parameters
    - Validation with range and value constraints
    - Support for scalar and multi-dimensional properties
    - Unit specification
    - Required/optional properties
    - Default values

Usage:
    >>> from usif import PropertyDefinition, Units
    >>>
    >>> # Define a scalar property
    >>> energy_prop = PropertyDefinition(
    ...     name='energy',
    ...     data_type=float,
    ...     units=Units.EV,
    ...     description='Total energy',
    ...     min_value=-1000.0,
    ...     max_value=1000.0
    ... )
    >>>
    >>> # Define a multi-dimensional property
    >>> force_prop = PropertyDefinition(
    ...     name='force',
    ...     data_type=tuple,
    ...     is_per_atom=True,
    ...     dimensions=(3,),
    ...     units=Units.EV_PER_ANGSTROM,
    ...     description='Force vector on atom'
    ... )
    >>>
    >>> # Validate a value
    >>> is_valid, message = energy_prop.validate_value(-10.5)
    >>> print(f"Valid: {is_valid}, Message: {message}")

See Also:
    - PropertyRegistry: Registry of built-in properties
    - PropertySerializer: Serialize property values
    - Units: Physical unit constants
"""

from dataclasses import dataclass
from typing import Any, Generic, List, Optional, Tuple, Type, TypeVar, Union

T = TypeVar("T")

# Supported data types for properties
SupportedTypes = (int, float, str, tuple, list, bool)
DataType = Union[Type[int], Type[float], Type[str], Type[tuple], Type[list], Type[bool]]


@dataclass
class PropertyDefinition(Generic[T]):
    """Generic property definition with type parameter"""

    name: str
    data_type: Type[T]
    is_per_atom: bool = False
    dimensions: Tuple[int, ...] = ()
    description: str = ""
    units: str = ""
    required: bool = False
    default_value: Optional[T] = None

    # Type constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[T]] = None

    def __post_init__(self) -> None:
        """Validate the property definition itself"""
        self._validate_definition()

    def _validate_definition(self) -> None:
        """Ensure the property definition is self-consistent"""
        # Validate data type is supported
        if self.data_type not in SupportedTypes:
            raise ValueError(
                f"Unsupported data type: {self.data_type}. "
                f"Supported types: {SupportedTypes}"
            )

        # Validate range constraints only apply to numeric types
        if (
            self.min_value is not None or self.max_value is not None
        ) and not issubclass(self.data_type, (int, float)):
            raise ValueError(
                "min_value/max_value constraints only applicable to numeric types (int, float)"
            )

        # Validate allowed_values match data_type
        if self.allowed_values is not None:
            for value in self.allowed_values:
                if not isinstance(value, self.data_type):
                    raise ValueError(
                        f"allowed_value {value} does not match data_type {self.data_type}"
                    )

        # Validate dimensions for non-scalar types
        if self.dimensions and self.data_type in (str,):
            raise ValueError("String properties cannot have dimensions")

        # Validate default value type
        if self.default_value is not None and not isinstance(
            self.default_value, self.data_type
        ):
            raise ValueError(
                f"default_value type {type(self.default_value)} does not match data_type {self.data_type}"
            )

    def is_scalar(self) -> bool:
        """Check if this is a scalar property"""
        return len(self.dimensions) == 0

    def validate_value(
        self, value: Any, num_atoms: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Enhanced validation with range and value checks"""

        # Get effective value (handle defaults)
        effective_value = self.get_effective_value(value)

        # Basic validation
        is_valid, message = self._basic_validation(effective_value, num_atoms)
        if not is_valid:
            return False, message

        # Range validation for numeric types
        if self.min_value is not None or self.max_value is not None:
            range_error = self._validate_range(effective_value)
            if range_error:
                return False, range_error

        # Allowed values validation
        if self.allowed_values is not None and effective_value is not None:
            if effective_value not in self.allowed_values:
                return (
                    False,
                    f"Value {effective_value} not in allowed values {self.allowed_values}",
                )

        return True, "Validation passed"

    def _basic_validation(
        self, value: Any, num_atoms: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Perform basic type and shape validation"""
        # Handle None values
        if value is None:
            if self.required and self.default_value is None:
                return False, "Value is required but None provided"
            return True, "Value is None but property is optional"

        # Type checking
        if not self._is_valid_type(value):
            return False, f"Expected type {self.data_type}, got {type(value)}"

        # Shape validation
        expected_shape = self.get_expected_shape(num_atoms)
        if expected_shape:
            shape_error = self._validate_shape(value, expected_shape)
            if shape_error:
                return False, shape_error

        return True, "Basic validation passed"

    def _is_valid_type(self, value: Any) -> bool:
        """Comprehensive type checking with flexibility"""
        if self.data_type == tuple:
            return isinstance(value, tuple)
        elif self.data_type == float:
            # Allow integers to be treated as floats
            return isinstance(value, (int, float))
        elif self.data_type == list:
            return isinstance(value, list)
        else:
            return isinstance(value, self.data_type)

    def _validate_range(self, value: Any) -> Optional[str]:
        """Validate numeric range constraints"""
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                return f"Value {value} below minimum {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return f"Value {value} above maximum {self.max_value}"

        # For arrays/tuples, validate each numeric element
        elif hasattr(value, "__iter__") and not isinstance(value, str):
            for i, elem in enumerate(value):
                if isinstance(elem, (int, float)):
                    elem_error = self._validate_range(elem)
                    if elem_error:
                        return f"Element {i}: {elem_error}"
                elif hasattr(elem, "__iter__") and not isinstance(elem, str):
                    # Handle nested structures
                    for j, sub_elem in enumerate(elem):
                        if isinstance(sub_elem, (int, float)):
                            sub_error = self._validate_range(sub_elem)
                            if sub_error:
                                return f"Element {i}[{j}]: {sub_error}"

        return None

    def _validate_shape(
        self, value: Any, expected_shape: Tuple[int, ...]
    ) -> Optional[str]:
        """Validate array shape with comprehensive checking"""

        def get_actual_shape(obj: Any, max_depth: int = 10) -> Tuple[int, ...]:
            """Recursively get the shape of nested structures"""
            if max_depth <= 0 or not hasattr(obj, "__len__") or isinstance(obj, str):
                return ()

            length = len(obj)
            if length == 0:
                return (0,)

            # Check if all elements have same structure
            first_elem_shape = (
                get_actual_shape(obj[0], max_depth - 1)
                if hasattr(obj[0], "__len__") and not isinstance(obj[0], str)
                else ()
            )

            # Verify consistent structure
            for elem in obj[1:]:
                elem_shape = (
                    get_actual_shape(elem, max_depth - 1)
                    if hasattr(elem, "__len__") and not isinstance(elem, str)
                    else ()
                )
                if elem_shape != first_elem_shape:
                    raise ValueError("Inconsistent nested structure")

            return (length,) + first_elem_shape

        try:
            actual_shape = get_actual_shape(value)
        except ValueError as e:
            return f"Inconsistent nested structure: {e}"

        if len(actual_shape) != len(expected_shape):
            return f"Expected {len(expected_shape)}D array, got {len(actual_shape)}D array with shape {actual_shape}"

        for dim, (expected, actual) in enumerate(zip(expected_shape, actual_shape)):
            if expected != actual:
                return f"Dimension {dim}: expected {expected}, got {actual}"

        return None

    def get_expected_shape(
        self, num_atoms: Optional[int] = None
    ) -> Optional[Tuple[int, ...]]:
        """Get expected shape for validation"""
        if self.is_per_atom:
            if num_atoms is None:
                # Cannot validate per-atom properties without atom count
                return None
            if num_atoms <= 0:
                raise ValueError(f"Invalid number of atoms: {num_atoms}")
            return (num_atoms,) + self.dimensions

        return self.dimensions if self.dimensions else None

    def get_effective_value(self, value: Any) -> Any:
        """Get the effective value (handle defaults)"""
        if value is None and self.default_value is not None:
            return self.default_value
        return value

    def describe(self) -> str:
        """Get human-readable description of the property"""
        parts = [f"'{self.name}'"]
        parts.append(f"type: {self.data_type.__name__}")

        if self.units:
            parts.append(f"units: {self.units}")

        if self.is_per_atom:
            parts.append("per-atom")

        if self.dimensions:
            parts.append(f"dims: {self.dimensions}")

        if self.required:
            parts.append("required")
        else:
            parts.append("optional")

        if self.default_value is not None:
            parts.append(f"default: {self.default_value}")

        if self.min_value is not None or self.max_value is not None:
            range_str = f"[{self.min_value or '-∞'}, {self.max_value or '∞'}]"
            parts.append(f"range: {range_str}")

        if self.allowed_values is not None:
            parts.append(f"allowed: {self.allowed_values}")

        if self.description:
            parts.append(f"desc: '{self.description}'")

        return " | ".join(parts)

    def __str__(self) -> str:
        """String representation"""
        return self.describe()

    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"PropertyDefinition(name='{self.name}', "
            f"data_type={self.data_type.__name__}, "
            f"is_per_atom={self.is_per_atom}, "
            f"dimensions={self.dimensions})"
        )


# Example usage and testing
if __name__ == "__main__":
    # Test the PropertyDefinition class
    energy_def = PropertyDefinition(
        name="energy",
        data_type=float,
        units="eV",
        description="Total energy of the system",
        min_value=-1000.0,
        max_value=1000.0,
        required=True,
    )

    force_def = PropertyDefinition(
        name="force",
        data_type=tuple,
        is_per_atom=True,
        dimensions=(3,),
        units="eV/Å",
        description="Force vector on each atom",
        required=False,
    )

    print(energy_def.describe())
    print(force_def.describe())

    # Test validation
    print("\nValidation tests:")
    print(energy_def.validate_value(-50.5))  # Should be valid
    print(energy_def.validate_value(-1500.0))  # Should be invalid
    print(
        force_def.validate_value(((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)), num_atoms=2)
    )  # Should be valid
