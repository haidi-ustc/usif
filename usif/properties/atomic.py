#!/usr/bin/env python3
"""Atomic property storage for USIF.

``AtomicProperties`` stores built-in per-site properties as efficient typed
fields and custom properties as JSON-safe values.  Since 6.6, built-in and
custom atomic properties can carry canonicalized unit metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

from usif.constants import SymmetryConstants
from usif.properties.values import (
    PropertyValueKind,
    as_numeric_scalar,
    as_scalar,
    as_tensor,
    as_vector,
    get_property_value_units,
    make_property_value,
    normalize_json_value,
    unwrap_property_value,
)
from usif.units import Units

_ATOMIC_BUILTINS = {"force", "charge", "magmom", "velocity"}
_ATOMIC_SCALARS = {"charge", "magmom"}
_ATOMIC_VECTORS = {"force", "velocity"}
_ATOMIC_DEFAULT_UNITS = {
    "force": Units.STANDARD_FORCE,
    "charge": Units.STANDARD_CHARGE,
    "magmom": Units.STANDARD_MAGNETIC_MOMENT,
    "velocity": Units.STANDARD_VELOCITY,
}


def validate_vector(value: Optional[Tuple[float, float, float]], name: str) -> None:
    """Validate that a vector has exactly 3 numeric elements."""
    if value is not None:
        if len(value) != 3:
            raise ValueError(f"{name} must be a 3-element tuple, got {len(value)} elements")
        if not all(isinstance(x, (int, float)) for x in value):
            raise TypeError(f"{name} must contain numeric values only")


@dataclass
class AtomicProperties:
    """Properties that can be attached to one atom/site."""

    force: Optional[Tuple[float, float, float]] = None
    charge: Optional[float] = None
    magmom: Optional[float] = None
    velocity: Optional[Tuple[float, float, float]] = None
    custom: Dict[str, Any] = field(default_factory=dict)
    units: Dict[str, str] = field(default_factory=dict)

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
        self.units = Units.canonicalize_units_map(self.units)
        self._adopt_custom_units()
        self._ensure_builtin_default_units()

    def _adopt_custom_units(self) -> None:
        for key, value in self.custom.items():
            units = get_property_value_units(value)
            if units:
                self.units.setdefault(key, units)

    def _ensure_builtin_default_units(self) -> None:
        for name, default_unit in _ATOMIC_DEFAULT_UNITS.items():
            if getattr(self, name, None) is not None:
                self.units.setdefault(name, Units.normalize_unit(default_unit) or default_unit)

    def get_all_properties(self) -> Dict[str, Any]:
        """Get all set property payloads without unit metadata sidecars."""
        props: Dict[str, Any] = {}
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

    def get_units_map(self) -> Dict[str, str]:
        """Return a copy of canonical unit metadata."""
        return dict(self.units)

    def get(self, name: str, default: Any = None) -> Any:
        """Return a built-in or custom atomic property payload without envelope."""
        if name in _ATOMIC_BUILTINS:
            value = getattr(self, name)
            return default if value is None else value
        return unwrap_property_value(self.custom.get(name, default))

    def has(self, name: str) -> bool:
        """Return True when a built-in or custom atomic property is set."""
        if name in _ATOMIC_BUILTINS:
            return getattr(self, name) is not None
        return name in self.custom

    def set(self, name: str, value: Any, *, units: str | None = None) -> "AtomicProperties":
        """Set a built-in or custom atomic property and return ``self``."""
        if name in _ATOMIC_VECTORS:
            return self.set_vector(name, value, units=units)
        if name in _ATOMIC_SCALARS:
            return self.set_scalar(name, value, units=units)
        normalized = normalize_json_value(value)
        if isinstance(normalized, list):
            return self.set_tensor(name, normalized, units=units)
        return self.set_custom(name, normalized, units=units)

    def remove(self, name: str) -> Any:
        """Remove a built-in or custom property and return its previous value."""
        self.units.pop(name, None)
        if name in _ATOMIC_BUILTINS:
            old = getattr(self, name)
            setattr(self, name, None)
            return old
        return unwrap_property_value(self.custom.pop(name, None))

    def set_scalar(
        self,
        name: str,
        value: Any,
        *,
        units: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AtomicProperties":
        """Set a scalar atomic property with optional unit metadata."""
        if name not in _ATOMIC_SCALARS:
            scalar = as_scalar(name, value)
            self.custom[name] = self._custom_payload(
                scalar, PropertyValueKind.SCALAR, units, description, metadata
            )
            if units is not None:
                self._set_units(name, units)
            return self
        setattr(self, name, as_numeric_scalar(name, value))
        self._set_units(name, units or _ATOMIC_DEFAULT_UNITS[name])
        return self

    def set_vector(
        self,
        name: str,
        value: Any,
        *,
        length: int = 3,
        units: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AtomicProperties":
        """Set a vector atomic property. Built-in vectors are stored as tuples."""
        vector = as_vector(name, value, length=length)
        if name in _ATOMIC_VECTORS:
            setattr(self, name, vector)
            self._set_units(name, units or _ATOMIC_DEFAULT_UNITS[name])
        else:
            self.custom[name] = self._custom_payload(
                list(vector), PropertyValueKind.VECTOR, units, description, metadata
            )
        return self

    def set_tensor(
        self,
        name: str,
        value: Any,
        *,
        shape: tuple[int, ...] | None = None,
        units: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AtomicProperties":
        """Set a custom tensor atomic property as a JSON-safe nested list."""
        self.custom[name] = self._custom_payload(
            as_tensor(name, value, shape=shape),
            PropertyValueKind.TENSOR,
            units,
            description,
            metadata,
        )
        if units is not None:
            self._set_units(name, units)
        return self

    def set_custom(
        self,
        name: str,
        value: Any,
        *,
        units: str | None = None,
        kind: PropertyValueKind | str = PropertyValueKind.CUSTOM,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AtomicProperties":
        """Set a JSON-compatible custom atomic property."""
        if name in _ATOMIC_BUILTINS:
            raise ValueError(f"'{name}' is a built-in property; use set('{name}', value)")
        self.custom[name] = self._custom_payload(
            normalize_json_value(value), kind, units, description, metadata
        )
        return self

    def _custom_payload(
        self,
        value: Any,
        kind: PropertyValueKind | str,
        units: str | None,
        description: str | None,
        metadata: dict[str, Any] | None,
    ) -> Any:
        if units is None and description is None and not metadata:
            return normalize_json_value(value)
        canonical_units = self._set_units("", units) if units is not None else None
        return make_property_value(
            value,
            kind,
            units=canonical_units,
            description=description,
            metadata=metadata,
        )

    def _set_units(self, name: str, units: str | None) -> str | None:
        if units is None:
            return None
        canonical = Units.normalize_unit(units)
        if name:
            if canonical:
                self.units[name] = canonical
            else:
                self.units.pop(name, None)
        return canonical

    def set_units(self, name: str, units: str | None) -> "AtomicProperties":
        """Set or clear unit metadata for a property name."""
        self._set_units(name, units)
        if name in self.custom and units is not None:
            self.custom[name] = make_property_value(
                unwrap_property_value(self.custom[name]),
                PropertyValueKind.CUSTOM,
                units=Units.normalize_unit(units),
            )
        return self

    def get_units(self, name: str, default: Any = None) -> Any:
        """Return canonical unit metadata for a property, if available."""
        return self.units.get(name, default)

    def clear_units(self, name: str) -> Any:
        """Remove unit metadata for a property and return the old unit."""
        return self.units.pop(name, None)

    def get_custom(self, name: str, default: Any = None) -> Any:
        """Return a custom atomic property payload without unit envelope."""
        return unwrap_property_value(self.custom.get(name, default))

    def get_custom_envelope(self, name: str, default: Any = None) -> Any:
        """Return the raw custom property payload, including unit envelope if present."""
        return self.custom.get(name, default)

    def has_force(self) -> bool:
        return self.force is not None

    def has_velocity(self) -> bool:
        return self.velocity is not None

    def has_charge(self) -> bool:
        return self.charge is not None

    def has_magmom(self) -> bool:
        return self.magmom is not None

    def to_array(self, property_name: str) -> Optional[np.ndarray]:
        if property_name not in ["force", "velocity"]:
            raise ValueError(f"Property '{property_name}' is not a vector property")
        value = getattr(self, property_name)
        if value is not None:
            return np.array(value)
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AtomicProperties":
        """Create an instance from a dictionary."""
        known_props: dict[str, Any] = {}
        custom_props = dict(data.get("custom", {}) or {})
        units = dict(data.get("units", {}) or {})

        for key, value in data.items():
            if key in {"custom", "units"}:
                continue
            if key in _ATOMIC_BUILTINS:
                known_props[key] = value
            else:
                custom_props[key] = value
        return cls(**known_props, custom=custom_props, units=units)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AtomicProperties):
            return NotImplemented

        def values_equal(v1, v2, is_vector: bool = False) -> bool:
            if v1 is None and v2 is None:
                return True
            if v1 is None or v2 is None:
                return False
            if is_vector:
                if hasattr(v1, "__len__") and hasattr(v2, "__len__"):
                    if len(v1) != len(v2):
                        return False
                    return all(
                        abs(float(a) - float(b)) < SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE
                        for a, b in zip(v1, v2)
                    )
                return False
            return abs(float(v1) - float(v2)) < SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE

        return (
            values_equal(self.force, other.force, is_vector=True)
            and values_equal(self.velocity, other.velocity, is_vector=True)
            and values_equal(self.charge, other.charge)
            and values_equal(self.magmom, other.magmom)
            and self.custom == other.custom
            and self.units == other.units
        )

    def __repr__(self) -> str:
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
        if self.units:
            parts.append(f"units={self.units}")
        return f"AtomicProperties({', '.join(parts)})"

    def copy(self) -> "AtomicProperties":
        import copy

        return AtomicProperties(
            force=copy.deepcopy(self.force) if self.force is not None else None,
            charge=copy.deepcopy(self.charge) if self.charge is not None else None,
            magmom=copy.deepcopy(self.magmom) if self.magmom is not None else None,
            velocity=copy.deepcopy(self.velocity) if self.velocity is not None else None,
            custom=copy.deepcopy(self.custom),
            units=copy.deepcopy(self.units),
        )
