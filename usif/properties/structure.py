#!/usr/bin/env python3
"""
USIF Structure Properties Module

This module provides the StructureProperties class for storing properties attached
to entire structures. These are structure-level properties like energy, stress,
volume, pressure, and temperature.

Main Class:
    StructureProperties: Properties attached to entire structures

Built-in Properties:
    - energy: Total energy (float, eV)
    - stress: Stress tensor in Voigt notation (6-element tuple, GPa)
    - volume: Cell volume (float, Å³)
    - pressure: Pressure (float, GPa)
    - temperature: Temperature (float, K)
    - custom: Dictionary for custom properties

Usage:
    >>> from usif import StructureProperties
    >>>
    >>> # Create structure properties
    >>> struct_props = StructureProperties(
    ...     energy=-10.5,
    ...     volume=179.4,
    ...     stress=(1.0, 1.0, 1.0, 0.0, 0.0, 0.0),
    ...     pressure=0.0,
    ...     temperature=300.0
    ... )
    >>>
    >>> # Add custom properties
    >>> struct_props.custom['calculator'] = 'VASP'
    >>> struct_props.custom['kpoints'] = '4x4x4'
    >>>
    >>> # Get all properties
    >>> all_props = struct_props.get_all_properties()
    >>>
    >>> # Use in USIFStructure
    >>> from usif import USIFStructure, StructureType, StorageMode
    >>> structure = USIFStructure(
    ...     structure_type=StructureType.CRYSTAL,
    ...     storage_mode=StorageMode.SYMMETRIC,
    ...     structure_properties=struct_props,
    ...     ...
    ... )

See Also:
    - AtomicProperties: Per-atom properties
    - USIFStructure: Structure with properties
    - PropertyDefinition: Property type definitions
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

from usif.constants import SymmetryConstants
from usif.properties.values import (
    as_numeric_scalar,
    as_numeric_tuple,
    as_scalar,
    as_tensor,
    infer_shape,
    normalize_json_value,
    stress_matrix_to_voigt,
    voigt_to_stress_matrix,
)


@dataclass
class StructureProperties:
    """Properties that can be attached to the entire structure"""

    energy: Optional[float] = None
    stress: Optional[Tuple[float, ...]] = None
    volume: Optional[float] = None
    pressure: Optional[float] = None
    temperature: Optional[float] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize structure properties."""
        if self.stress is not None:
            if infer_shape(self.stress) == (3, 3):
                self.stress = stress_matrix_to_voigt(self.stress)
            else:
                self.stress = as_numeric_tuple("stress", self.stress, length=6)

        for prop_name in ["energy", "volume", "pressure", "temperature"]:
            value = getattr(self, prop_name)
            if value is not None:
                setattr(self, prop_name, as_numeric_scalar(prop_name, value))

        self.custom = {key: normalize_json_value(value) for key, value in self.custom.items()}


    def get(self, name: str, default: Any = None) -> Any:
        """Return a built-in or custom structure property value."""
        if name in {"energy", "stress", "volume", "pressure", "temperature"}:
            value = getattr(self, name)
            return default if value is None else value
        return self.custom.get(name, default)

    def has(self, name: str) -> bool:
        """Return True when a built-in or custom structure property is set."""
        return self.get(name, None) is not None if name in {"energy", "stress", "volume", "pressure", "temperature"} else name in self.custom

    def set(self, name: str, value: Any) -> "StructureProperties":
        """Set a built-in or custom structure property and return ``self`` for chaining."""
        if name == "stress":
            return self.set_tensor(name, value)
        if name in {"energy", "volume", "pressure", "temperature"}:
            return self.set_scalar(name, value)
        return self.set_custom(name, value)

    def remove(self, name: str) -> Any:
        """Remove a built-in or custom structure property and return the old value."""
        if name in {"energy", "stress", "volume", "pressure", "temperature"}:
            old = getattr(self, name)
            setattr(self, name, None)
            return old
        return self.custom.pop(name, None)

    def set_scalar(self, name: str, value: Any) -> "StructureProperties":
        """Set a scalar structure property. Built-in scalar names are validated."""
        if name not in {"energy", "volume", "pressure", "temperature"}:
            self.custom[name] = as_scalar(name, value)
            return self
        setattr(self, name, as_numeric_scalar(name, value))
        return self

    def set_vector(self, name: str, value: Any, *, length: int | None = None) -> "StructureProperties":
        """Set a custom vector structure property as a JSON-safe list."""
        expected = 3 if length is None else length
        self.custom[name] = list(as_numeric_tuple(name, value, length=expected))
        return self

    def set_tensor(self, name: str, value: Any, *, shape: tuple[int, ...] | None = None) -> "StructureProperties":
        """Set a tensor structure property. ``stress`` accepts Voigt or 3x3 matrix form."""
        if name == "stress":
            actual_shape = infer_shape(value)
            if actual_shape == (3, 3):
                self.stress = stress_matrix_to_voigt(value)
            else:
                self.stress = as_numeric_tuple("stress", value, length=6)
            return self
        self.custom[name] = as_tensor(name, value, shape=shape)
        return self

    def set_custom(self, name: str, value: Any) -> "StructureProperties":
        """Set a JSON-compatible custom structure property."""
        if name in {"energy", "stress", "volume", "pressure", "temperature"}:
            raise ValueError(f"'{name}' is a built-in property; use set('{name}', value)")
        self.custom[name] = normalize_json_value(value)
        return self

    def get_custom(self, name: str, default: Any = None) -> Any:
        """Return a custom structure property value."""
        return self.custom.get(name, default)

    def stress_matrix(self) -> Optional[list[list[float]]]:
        """Return the stress tensor as a symmetric 3x3 matrix when set."""
        if self.stress is None:
            return None
        return voigt_to_stress_matrix(self.stress)

    def get_all_properties(self) -> Dict[str, Any]:
        """Get all properties as dictionary

        Returns:
            Dictionary containing all set properties, including custom ones
        """
        props = {}
        if self.energy is not None:
            props["energy"] = self.energy
        if self.stress is not None:
            props["stress"] = self.stress
        if self.volume is not None:
            props["volume"] = self.volume
        if self.pressure is not None:
            props["pressure"] = self.pressure
        if self.temperature is not None:
            props["temperature"] = self.temperature
        props.update(self.custom)
        return props

    def has_energy(self) -> bool:
        """Check if energy is set

        Returns:
            True if energy is set, False otherwise
        """
        return self.energy is not None

    def has_stress(self) -> bool:
        """Check if stress tensor is set

        Returns:
            True if stress tensor is set, False otherwise
        """
        return self.stress is not None

    def has_volume(self) -> bool:
        """Check if volume is set

        Returns:
            True if volume is set, False otherwise
        """
        return self.volume is not None

    def has_pressure(self) -> bool:
        """Check if pressure is set

        Returns:
            True if pressure is set, False otherwise
        """
        return self.pressure is not None

    def has_temperature(self) -> bool:
        """Check if temperature is set

        Returns:
            True if temperature is set, False otherwise
        """
        return self.temperature is not None

    def to_stress_array(self) -> Optional[np.ndarray]:
        """Convert stress tensor to numpy array

        Returns:
            Numpy array of the stress tensor, or None if stress is not set
        """
        if self.stress is not None:
            return np.array(self.stress)
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructureProperties":
        """Create instance from dictionary

        Args:
            data: Dictionary containing property data

        Returns:
            StructureProperties instance

        Examples:
            >>> data = {'energy': -10.5, 'volume': 179.4, 'custom_tag': 'value'}
            >>> props = StructureProperties.from_dict(data)
        """
        known_fields = {"energy", "stress", "volume", "pressure", "temperature"}
        known_props = {}
        custom_props = dict(data.get("custom", {}) or {})

        for key, value in data.items():
            if key == "custom":
                continue
            if key in known_fields:
                known_props[key] = value
            else:
                custom_props[key] = value

        return cls(**known_props, custom=custom_props)

    def __eq__(self, other: object) -> bool:
        """Compare two StructureProperties instances for equality

        Uses tolerance-based comparison for numeric values and vectors.
        """
        if not isinstance(other, StructureProperties):
            return NotImplemented

        def values_equal(v1, v2, is_vector: bool = False) -> bool:
            """Compare two values with tolerance"""
            if v1 is None and v2 is None:
                return True
            if v1 is None or v2 is None:
                return False

            if is_vector:
                # Handle numpy arrays and other sequence types
                if hasattr(v1, "__len__") and hasattr(v2, "__len__"):
                    if len(v1) != len(v2):
                        return False
                    return all(
                        abs(float(a) - float(b))
                        < SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE
                        for a, b in zip(v1, v2)
                    )
                else:
                    return False
            else:
                # Scalar comparison
                return (
                    abs(float(v1) - float(v2))
                    < SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE
                )

        return (
            values_equal(self.energy, other.energy)
            and values_equal(self.stress, other.stress, is_vector=True)
            and values_equal(self.volume, other.volume)
            and values_equal(self.pressure, other.pressure)
            and values_equal(self.temperature, other.temperature)
            and self.custom == other.custom
        )

    def __repr__(self) -> str:
        """Enhanced representation showing set properties"""
        parts = []
        if self.energy is not None:
            parts.append(f"energy={self.energy}")
        if self.stress is not None:
            parts.append(f"stress={self.stress}")
        if self.volume is not None:
            parts.append(f"volume={self.volume}")
        if self.pressure is not None:
            parts.append(f"pressure={self.pressure}")
        if self.temperature is not None:
            parts.append(f"temperature={self.temperature}")
        if self.custom:
            parts.append(f"custom={self.custom}")

        return f"StructureProperties({', '.join(parts)})"

    def copy(self) -> "StructureProperties":
        """Create a deep copy of the StructureProperties instance

        Returns:
            New StructureProperties instance with copied data
        """
        import copy

        return StructureProperties(
            energy=self.energy,
            stress=copy.deepcopy(self.stress) if self.stress is not None else None,
            volume=self.volume,
            pressure=self.pressure,
            temperature=self.temperature,
            custom=copy.deepcopy(self.custom),
        )
