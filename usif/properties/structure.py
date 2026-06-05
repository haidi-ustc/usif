#!/usr/bin/env python3
"""Structure-level property storage for USIF.

``StructureProperties`` stores built-in structure properties as efficient typed
fields and custom properties as JSON-safe values.  Since 6.6, both built-in and
custom properties can carry unit metadata.  Unit strings are normalized through
``usif.units.Units`` so Unicode and ASCII spellings such as ``Å²``/``Å^2`` and
``Ang^2``/``angstrom^2`` are treated equivalently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

from usif.constants import SymmetryConstants
from usif.properties.values import (
    PropertyValueKind,
    as_numeric_scalar,
    as_numeric_tuple,
    as_scalar,
    as_tensor,
    get_property_value_units,
    infer_shape,
    make_property_value,
    normalize_json_value,
    stress_matrix_to_voigt,
    unwrap_property_value,
    voigt_to_stress_matrix,
)
from usif.units import Units

_STRUCTURE_BUILTINS = {"energy", "stress", "volume", "pressure", "temperature"}
_STRUCTURE_SCALARS = {"energy", "volume", "pressure", "temperature"}
_STRUCTURE_DEFAULT_UNITS = {
    "energy": Units.STANDARD_ENERGY,
    "stress": Units.STANDARD_PRESSURE,
    "volume": Units.STANDARD_VOLUME,
    "pressure": Units.STANDARD_PRESSURE,
    "temperature": Units.STANDARD_TEMPERATURE,
}


@dataclass
class StructureProperties:
    """Properties that can be attached to an entire structure."""

    energy: Optional[float] = None
    stress: Optional[Tuple[float, ...]] = None
    volume: Optional[float] = None
    pressure: Optional[float] = None
    temperature: Optional[float] = None
    custom: Dict[str, Any] = field(default_factory=dict)
    units: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate values, normalize custom payloads, and canonicalize units."""
        if self.stress is not None:
            if infer_shape(self.stress) == (3, 3):
                self.stress = stress_matrix_to_voigt(self.stress)
            else:
                self.stress = as_numeric_tuple("stress", self.stress, length=6)

        for prop_name in _STRUCTURE_SCALARS:
            value = getattr(self, prop_name)
            if value is not None:
                setattr(self, prop_name, as_numeric_scalar(prop_name, value))

        self.custom = {key: normalize_json_value(value) for key, value in self.custom.items()}
        self.units = Units.canonicalize_units_map(self.units)
        self._adopt_custom_units()
        self._ensure_builtin_default_units()

    def _adopt_custom_units(self) -> None:
        """Populate ``units`` from custom PropertyValue envelopes when present."""
        for key, value in self.custom.items():
            units = get_property_value_units(value)
            if units:
                self.units.setdefault(key, units)

    def _ensure_builtin_default_units(self) -> None:
        for name, default_unit in _STRUCTURE_DEFAULT_UNITS.items():
            if getattr(self, name, None) is not None:
                self.units.setdefault(name, Units.normalize_unit(default_unit) or default_unit)

    def get(self, name: str, default: Any = None) -> Any:
        """Return a built-in or custom structure property value without unit envelope."""
        if name in _STRUCTURE_BUILTINS:
            value = getattr(self, name)
            return default if value is None else value
        return unwrap_property_value(self.custom.get(name, default))

    def has(self, name: str) -> bool:
        """Return True when a built-in or custom structure property is set."""
        if name in _STRUCTURE_BUILTINS:
            return getattr(self, name) is not None
        return name in self.custom

    def set(self, name: str, value: Any, *, units: str | None = None) -> "StructureProperties":
        """Set a built-in or custom structure property and return ``self``."""
        if name == "stress":
            return self.set_tensor(name, value, units=units)
        if name in _STRUCTURE_SCALARS:
            return self.set_scalar(name, value, units=units)
        normalized = normalize_json_value(value)
        if isinstance(normalized, list):
            return self.set_tensor(name, normalized, units=units)
        return self.set_custom(name, normalized, units=units)

    def remove(self, name: str) -> Any:
        """Remove a built-in or custom property and return its previous value."""
        self.units.pop(name, None)
        if name in _STRUCTURE_BUILTINS:
            old = getattr(self, name)
            setattr(self, name, None)
            return old
        old = self.custom.pop(name, None)
        return unwrap_property_value(old)

    def set_scalar(
        self,
        name: str,
        value: Any,
        *,
        units: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "StructureProperties":
        """Set a scalar structure property with optional unit metadata."""
        if name not in _STRUCTURE_SCALARS:
            scalar = as_scalar(name, value)
            self.custom[name] = self._custom_payload(
                scalar, PropertyValueKind.SCALAR, units, description, metadata
            )
            if units is not None:
                self._set_units(name, units)
            return self
        setattr(self, name, as_numeric_scalar(name, value))
        self._set_units(name, units or _STRUCTURE_DEFAULT_UNITS[name])
        return self

    def set_vector(
        self,
        name: str,
        value: Any,
        *,
        length: int | None = None,
        units: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "StructureProperties":
        """Set a custom vector structure property as a JSON-safe list."""
        expected = 3 if length is None else length
        vector = list(as_numeric_tuple(name, value, length=expected))
        self.custom[name] = self._custom_payload(
            vector, PropertyValueKind.VECTOR, units, description, metadata
        )
        if units is not None:
            self._set_units(name, units)
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
    ) -> "StructureProperties":
        """Set a tensor property. ``stress`` accepts Voigt or 3x3 matrix form."""
        if name == "stress":
            actual_shape = infer_shape(value)
            if actual_shape == (3, 3):
                self.stress = stress_matrix_to_voigt(value)
            else:
                self.stress = as_numeric_tuple("stress", value, length=6)
            self._set_units("stress", units or _STRUCTURE_DEFAULT_UNITS["stress"])
            return self
        tensor = as_tensor(name, value, shape=shape)
        self.custom[name] = self._custom_payload(
            tensor, PropertyValueKind.TENSOR, units, description, metadata
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
    ) -> "StructureProperties":
        """Set a JSON-compatible custom structure property.

        When units, description, or metadata are provided, the value is stored as
        a ``PropertyValue`` envelope.  ``get()`` and ``get_custom()`` still return
        the bare payload value for ergonomic use.
        """
        if name in _STRUCTURE_BUILTINS:
            raise ValueError(f"'{name}' is a built-in property; use set('{name}', value)")
        normalized = normalize_json_value(value)
        self.custom[name] = self._custom_payload(normalized, kind, units, description, metadata)
        if units is not None:
            self._set_units(name, units)
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

    def set_units(self, name: str, units: str | None) -> "StructureProperties":
        """Set or clear unit metadata for a property name."""
        self._set_units(name, units)
        if name in self.custom and units is not None:
            value = unwrap_property_value(self.custom[name])
            self.custom[name] = make_property_value(
                value,
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
        """Return a custom structure property payload without unit envelope."""
        return unwrap_property_value(self.custom.get(name, default))

    def get_custom_envelope(self, name: str, default: Any = None) -> Any:
        """Return the raw custom property payload, including unit envelope if present."""
        return self.custom.get(name, default)

    def stress_matrix(self) -> Optional[list[list[float]]]:
        """Return the stress tensor as a symmetric 3x3 matrix when set."""
        if self.stress is None:
            return None
        return voigt_to_stress_matrix(self.stress)

    def get_all_properties(self) -> Dict[str, Any]:
        """Get all set property payloads without unit metadata sidecars."""
        props: Dict[str, Any] = {}
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

    def get_units_map(self) -> Dict[str, str]:
        """Return a copy of canonical unit metadata."""
        return dict(self.units)

    def has_energy(self) -> bool:
        return self.energy is not None

    def has_stress(self) -> bool:
        return self.stress is not None

    def has_volume(self) -> bool:
        return self.volume is not None

    def has_pressure(self) -> bool:
        return self.pressure is not None

    def has_temperature(self) -> bool:
        return self.temperature is not None

    def to_stress_array(self) -> Optional[np.ndarray]:
        if self.stress is not None:
            return np.array(self.stress)
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructureProperties":
        """Create an instance from a dictionary."""
        known_props: dict[str, Any] = {}
        custom_props = dict(data.get("custom", {}) or {})
        units = dict(data.get("units", {}) or {})

        for key, value in data.items():
            if key in {"custom", "units"}:
                continue
            if key in _STRUCTURE_BUILTINS:
                known_props[key] = value
            else:
                custom_props[key] = value
        return cls(**known_props, custom=custom_props, units=units)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StructureProperties):
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
            values_equal(self.energy, other.energy)
            and values_equal(self.stress, other.stress, is_vector=True)
            and values_equal(self.volume, other.volume)
            and values_equal(self.pressure, other.pressure)
            and values_equal(self.temperature, other.temperature)
            and self.custom == other.custom
            and self.units == other.units
        )

    def __repr__(self) -> str:
        parts = []
        if self.energy is not None:
            parts.append(f"energy={self.energy}")
        if self.volume is not None:
            parts.append(f"volume={self.volume}")
        if self.stress is not None:
            parts.append(f"stress={self.stress}")
        if self.pressure is not None:
            parts.append(f"pressure={self.pressure}")
        if self.temperature is not None:
            parts.append(f"temperature={self.temperature}")
        if self.custom:
            parts.append(f"custom={self.custom}")
        if self.units:
            parts.append(f"units={self.units}")
        return f"StructureProperties({', '.join(parts)})"

    def copy(self) -> "StructureProperties":
        import copy

        return StructureProperties(
            energy=self.energy,
            stress=copy.deepcopy(self.stress) if self.stress is not None else None,
            volume=self.volume,
            pressure=self.pressure,
            temperature=self.temperature,
            custom=copy.deepcopy(self.custom),
            units=copy.deepcopy(self.units),
        )
