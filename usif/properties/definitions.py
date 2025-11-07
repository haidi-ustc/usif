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

from typing import TypeVar, Generic, Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class PropertyDefinition(Generic[T]):
    """Generic property definition with type parameter"""
    
    name: str
    data_type: type
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

    def is_scalar(self) -> bool:
        return len(self.dimensions) == 0

    def validate_value(self, value: Any, num_atoms: Optional[int] = None) -> Tuple[bool, str]:
        """Enhanced validation with range and value checks"""
        
        # Basic validation
        is_valid, message = self._basic_validation(value, num_atoms)
        if not is_valid:
            return False, message

        # Range validation for numeric types
        if self.min_value is not None or self.max_value is not None:
            range_error = self._validate_range(value)
            if range_error:
                return False, range_error

        # Allowed values validation
        if self.allowed_values is not None:
            if value not in self.allowed_values:
                return False, f"Value {value} not in allowed values {self.allowed_values}"

        return True, "Validation passed"

    def _basic_validation(self, value: Any, num_atoms: Optional[int] = None) -> Tuple[bool, str]:
        """Perform basic type and shape validation"""
        if value is None:
            if self.required:
                return False, "Value is required but None provided"
            return True, "Optional value is None"

        if not isinstance(value, self.data_type):
            return False, f"Expected type {self.data_type}, got {type(value)}"

        # Shape validation
        expected_shape = self.get_expected_shape(num_atoms)
        if expected_shape:
            shape_error = self._validate_shape(value, expected_shape)
            if shape_error:
                return False, shape_error

        return True, "Basic validation passed"

    def _validate_range(self, value: Any) -> Optional[str]:
        """Validate numeric range"""
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                return f"Value {value} below minimum {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return f"Value {value} above maximum {self.max_value}"
        
        # For arrays, validate each element
        elif hasattr(value, '__iter__') and not isinstance(value, str):
            for i, elem in enumerate(value):
                elem_error = self._validate_range(elem)
                if elem_error:
                    return f"Element {i}: {elem_error}"
        
        return None

    def _validate_shape(self, value: Any, expected_shape: Tuple[int, ...]) -> Optional[str]:
        """Validate array shape"""
        if hasattr(value, 'shape'):  # numpy array
            if value.shape != expected_shape:
                return f"Expected shape {expected_shape}, got {value.shape}"
        elif hasattr(value, '__len__'):
            if len(value) != expected_shape[0]:
                return f"Expected length {expected_shape[0]}, got {len(value)}"
            # Recursively check nested dimensions
            if len(expected_shape) > 1 and hasattr(value[0], '__len__'):
                for i, elem in enumerate(value):
                    elem_error = self._validate_shape(elem, expected_shape[1:])
                    if elem_error:
                        return f"Element {i}: {elem_error}"
        return None

    def get_expected_shape(self, num_atoms: Optional[int] = None) -> Tuple[int, ...]:
        """Get expected shape for validation"""
        if self.is_per_atom and num_atoms is not None:
            return (num_atoms,) + self.dimensions
        return self.dimensions

