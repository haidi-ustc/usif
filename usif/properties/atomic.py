#!/usr/bin/env python3
"""
USIF Atomic Properties Module

This module provides the AtomicProperties class for storing properties attached
to individual atoms. These properties are per-atom and can include forces, charges,
magnetic moments, velocities, and custom properties.

Main Class:
    AtomicProperties: Properties attached to individual atoms

Built-in Properties:
    - force: Force vector (3D tuple, eV/Å)
    - charge: Atomic charge (float, e)
    - magmom: Magnetic moment (float, μB)
    - velocity: Atomic velocity (3D tuple, Å/fs)
    - custom: Dictionary for custom properties

Usage:
    >>> from usif import AtomicProperties
    >>>
    >>> # Create atomic properties
    >>> atom_props = AtomicProperties(
    ...     force=(0.1, 0.2, 0.3),
    ...     charge=0.5,
    ...     magmom=2.0,
    ...     velocity=(0.0, 0.0, 0.0)
    ... )
    >>>
    >>> # Add custom properties
    >>> atom_props.custom['tag'] = 'surface'
    >>> atom_props.custom['label'] = 'Si1'
    >>>
    >>> # Get all properties
    >>> all_props = atom_props.get_all_properties()
    >>>
    >>> # Use in AtomSite
    >>> from usif.structures.sites import AtomSite
    >>> site = AtomSite(
    ...     atomic_number=14,
    ...     coords=(0.0, 0.0, 0.0),
    ...     properties=atom_props
    ... )

See Also:
    - StructureProperties: Structure-level properties
    - AtomSite: Atomic site with properties
    - PropertyDefinition: Property type definitions
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

from usif.constants import SymmetryConstants
from usif.properties.values import as_numeric_scalar, as_scalar, as_tensor, as_vector, normalize_json_value


def validate_vector(value: Optional[Tuple[float, float, float]], name: str) -> None:
    """Validate that a vector has exactly 3 elements.

    Args:
        value: The vector to validate
        name: Name of the vector property for error messages

    Raises:
        ValueError: If vector doesn't have exactly 3 elements
        TypeError: If vector contains non-numeric values
    """
    if value is not None:
        if len(value) != 3:
            raise ValueError(
                f"{name} must be a 3-element tuple, got {len(value)} elements"
            )
        if not all(isinstance(x, (int, float)) for x in value):
            raise TypeError(f"{name} must contain numeric values only")


@dataclass
class AtomicProperties:
    """Properties that can be attached to individual atoms"""

    force: Optional[Tuple[float, float, float]] = None
    charge: Optional[float] = None
    magmom: Optional[float] = None
    velocity: Optional[Tuple[float, float, float]] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize initialization data."""
        if self.force is not None:
            self.force = as_vector("force", self.force, length=3)  # type: ignore[assignment]
        if self.velocity is not None:
            self.velocity = as_vector("velocity", self.velocity, length=3)  # type: ignore[assignment]
        if self.charge is not None:
            self.charge = as_numeric_scalar("charge", self.charge)
        if self.magmom is not None:
            self.magmom = as_numeric_scalar("magmom", self.magmom)
        self.custom = {key: normalize_json_value(value) for key, value in self.custom.items()}

    def get_all_properties(self) -> Dict[str, Any]:
        """Get all properties as dictionary

        Returns:
            Dictionary containing all set properties, including custom ones
        """
        props = {}
        if self.force is not None:
            props["force"] = self.force
        if self.charge is not None:
            props["charge"] = self.charge
        if self.magmom is not None:
            props["magmom"] = self.magmom
        if self.velocity is not None:
            props["velocity"] = self.velocity
        props.update(self.custom)
        return props


    def get(self, name: str, default: Any = None) -> Any:
        """Return a built-in or custom atomic property value."""
        if name in {"force", "charge", "magmom", "velocity"}:
            value = getattr(self, name)
            return default if value is None else value
        return self.custom.get(name, default)

    def has(self, name: str) -> bool:
        """Return True when a built-in or custom atomic property is set."""
        return self.get(name, None) is not None if name in {"force", "charge", "magmom", "velocity"} else name in self.custom

    def set(self, name: str, value: Any) -> "AtomicProperties":
        """Set a built-in or custom atomic property and return ``self`` for chaining."""
        if name in {"force", "velocity"}:
            return self.set_vector(name, value)
        if name in {"charge", "magmom"}:
            return self.set_scalar(name, value)
        return self.set_custom(name, value)

    def remove(self, name: str) -> Any:
        """Remove a built-in or custom atomic property and return the old value."""
        if name in {"force", "charge", "magmom", "velocity"}:
            old = getattr(self, name)
            setattr(self, name, None)
            return old
        return self.custom.pop(name, None)

    def set_scalar(self, name: str, value: Any) -> "AtomicProperties":
        """Set a scalar atomic property. Built-in scalar names are validated."""
        if name not in {"charge", "magmom"}:
            self.custom[name] = as_scalar(name, value)
            return self
        setattr(self, name, as_numeric_scalar(name, value))
        return self

    def set_vector(self, name: str, value: Any, *, length: int = 3) -> "AtomicProperties":
        """Set a vector atomic property. Built-in vectors are stored as tuples."""
        vector = as_vector(name, value, length=length)
        if name in {"force", "velocity"}:
            setattr(self, name, vector)
        else:
            self.custom[name] = list(vector)
        return self

    def set_tensor(self, name: str, value: Any, *, shape: tuple[int, ...] | None = None) -> "AtomicProperties":
        """Set a custom tensor atomic property as a JSON-safe nested list."""
        self.custom[name] = as_tensor(name, value, shape=shape)
        return self

    def set_custom(self, name: str, value: Any) -> "AtomicProperties":
        """Set a JSON-compatible custom atomic property."""
        if name in {"force", "charge", "magmom", "velocity"}:
            raise ValueError(f"'{name}' is a built-in property; use set('{name}', value)")
        self.custom[name] = normalize_json_value(value)
        return self

    def get_custom(self, name: str, default: Any = None) -> Any:
        """Return a custom atomic property value."""
        return self.custom.get(name, default)

    def has_force(self) -> bool:
        """Check if force is set

        Returns:
            True if force is set, False otherwise
        """
        return self.force is not None

    def has_velocity(self) -> bool:
        """Check if velocity is set

        Returns:
            True if velocity is set, False otherwise
        """
        return self.velocity is not None

    def has_charge(self) -> bool:
        """Check if charge is set

        Returns:
            True if charge is set, False otherwise
        """
        return self.charge is not None

    def has_magmom(self) -> bool:
        """Check if magnetic moment is set

        Returns:
            True if magnetic moment is set, False otherwise
        """
        return self.magmom is not None

    def to_array(self, property_name: str) -> Optional[np.ndarray]:
        """Convert vector property to numpy array

        Args:
            property_name: Name of the vector property ('force' or 'velocity')

        Returns:
            Numpy array of the vector, or None if property is not set

        Raises:
            ValueError: If property_name is not a vector property
        """
        if property_name not in ["force", "velocity"]:
            raise ValueError(f"Property '{property_name}' is not a vector property")

        value = getattr(self, property_name)
        if value is not None:
            return np.array(value)
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AtomicProperties":
        """Create instance from dictionary

        Args:
            data: Dictionary containing property data

        Returns:
            AtomicProperties instance

        Examples:
            >>> data = {'force': (1.0, 2.0, 3.0), 'charge': 0.5, 'custom_tag': 'value'}
            >>> props = AtomicProperties.from_dict(data)
        """
        known_fields = {"force", "charge", "magmom", "velocity"}
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
        """Compare two AtomicProperties instances for equality

        Uses tolerance-based comparison for numeric values and vectors.
        """
        if not isinstance(other, AtomicProperties):
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
            values_equal(self.force, other.force, is_vector=True)
            and values_equal(self.velocity, other.velocity, is_vector=True)
            and values_equal(self.charge, other.charge)
            and values_equal(self.magmom, other.magmom)
            and self.custom == other.custom
        )

    def __repr__(self) -> str:
        """Enhanced representation showing set properties"""
        parts = []
        if self.force is not None:
            parts.append(f"force={self.force}")
        if self.charge is not None:
            parts.append(f"charge={self.charge}")
        if self.magmom is not None:
            parts.append(f"magmom={self.magmom}")
        if self.velocity is not None:
            parts.append(f"velocity={self.velocity}")
        if self.custom:
            parts.append(f"custom={self.custom}")

        return f"AtomicProperties({', '.join(parts)})"

    def copy(self) -> "AtomicProperties":
        """Create a deep copy of the AtomicProperties instance

        Returns:
            New AtomicProperties instance with copied data
        """
        import copy

        return AtomicProperties(
            force=copy.deepcopy(self.force) if self.force is not None else None,
            charge=copy.deepcopy(self.charge) if self.charge is not None else None,
            magmom=copy.deepcopy(self.magmom) if self.magmom is not None else None,
            velocity=(
                copy.deepcopy(self.velocity) if self.velocity is not None else None
            ),
            custom=copy.deepcopy(self.custom),
        )
