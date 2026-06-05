"""Property definition registry for USIF.

The registry is an instance object.  Code that needs isolation should call
``create_default_registry()`` and pass that registry into codecs or services.
``DEFAULT_REGISTRY`` is the process-wide registry containing the built-in USIF
properties.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Iterable, List, Optional, Tuple

from usif.properties.definitions import PropertyDefinition

logger = logging.getLogger(__name__)

_RESERVED_NAMES = {"type", "name", "units", "description", "id", "class"}


class PropertyRegistry:
    """Mutable registry of property definitions.

    ``PropertyRegistry`` is intentionally instance-based: callers create an
    isolated registry when they need custom definitions without global state.
    """

    BUILTIN_NAMES = frozenset(
        {
            "force",
            "charge",
            "magmom",
            "velocity",
            "energy",
            "stress",
            "volume",
            "pressure",
            "temperature",
        }
    )

    def __init__(
        self,
        definitions: Optional[Iterable[PropertyDefinition]] = None,
        *,
        builtin_names: Optional[Iterable[str]] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._properties: Dict[str, PropertyDefinition] = {}
        self._builtin_properties = set(builtin_names or ())
        for definition in definitions or ():
            self.register(definition, allow_builtin=True)

    @classmethod
    def builtins(cls) -> List[PropertyDefinition]:
        """Return the built-in USIF property definitions."""
        from usif.units import Units

        return [
            PropertyDefinition(
                "force",
                tuple,
                is_per_atom=True,
                dimensions=(3,),
                description="Force on atom",
                units=Units.EV_PER_ANGSTROM,
            ),
            PropertyDefinition(
                "charge",
                float,
                is_per_atom=True,
                description="Atomic charge",
                units=Units.ELEMENTARY_CHARGE,
            ),
            PropertyDefinition(
                "magmom",
                float,
                is_per_atom=True,
                description="Magnetic moment",
                units=Units.BOHR_MAGNETON,
            ),
            PropertyDefinition(
                "velocity",
                tuple,
                is_per_atom=True,
                dimensions=(3,),
                description="Atomic velocity",
                units=Units.ANGSTROM_PER_FS,
            ),
            PropertyDefinition("energy", float, description="Total energy", units=Units.EV),
            PropertyDefinition(
                "stress",
                tuple,
                dimensions=(6,),
                description="Stress tensor (Voigt notation)",
                units=Units.GPA,
            ),
            PropertyDefinition(
                "volume", float, description="Cell volume", units=Units.ANGSTROM_CUBED
            ),
            PropertyDefinition("pressure", float, description="Pressure", units=Units.GPA),
            PropertyDefinition(
                "temperature", float, description="Temperature", units=Units.KELVIN
            ),
        ]

    @classmethod
    def with_builtins(cls) -> "PropertyRegistry":
        """Create a registry populated with the built-in USIF definitions."""
        return cls(cls.builtins(), builtin_names=cls.BUILTIN_NAMES)

    def copy(self) -> "PropertyRegistry":
        """Return an isolated copy of this registry."""
        with self._lock:
            return PropertyRegistry(
                self._properties.values(), builtin_names=self._builtin_properties
            )

    def register(
        self, prop_def: PropertyDefinition, *, allow_builtin: bool = False
    ) -> None:
        """Register or replace a property definition."""
        if not isinstance(prop_def, PropertyDefinition):
            raise TypeError(f"Expected PropertyDefinition, got {type(prop_def)}")
        if not prop_def.name or not isinstance(prop_def.name, str):
            raise ValueError("Property definition must have a valid name")
        if prop_def.name in _RESERVED_NAMES:
            raise ValueError(f"Property name '{prop_def.name}' is reserved")

        with self._lock:
            if prop_def.name in self._builtin_properties and not allow_builtin:
                logger.warning("Replacing built-in property definition: %s", prop_def.name)
            elif prop_def.name in self._properties:
                logger.info("Replacing property definition: %s", prop_def.name)
            self._properties[prop_def.name] = prop_def

    def get(self, name: str) -> Optional[PropertyDefinition]:
        """Return a property definition by name, or ``None`` when absent."""
        with self._lock:
            return self._properties.get(name)

    def get_required(self, name: str) -> PropertyDefinition:
        """Return a property definition or raise ``KeyError``."""
        prop_def = self.get(name)
        if prop_def is None:
            raise KeyError(
                f"Property '{name}' not found in registry. "
                f"Available properties: {self.list_properties()}"
            )
        return prop_def

    def is_atomic_property(self, name: str) -> bool:
        prop_def = self.get(name)
        return prop_def.is_per_atom if prop_def else False

    def is_structure_property(self, name: str) -> bool:
        prop_def = self.get(name)
        return not prop_def.is_per_atom if prop_def else False

    def is_builtin(self, name: str) -> bool:
        return name in self._builtin_properties

    def exists(self, name: str) -> bool:
        with self._lock:
            return name in self._properties

    def list_properties(
        self, *, atomic_only: bool = False, structure_only: bool = False
    ) -> List[str]:
        if atomic_only and structure_only:
            raise ValueError("Cannot specify both atomic_only and structure_only")
        with self._lock:
            names = list(self._properties.keys())
        if atomic_only:
            return [name for name in names if self.is_atomic_property(name)]
        if structure_only:
            return [name for name in names if self.is_structure_property(name)]
        return names

    def unregister(self, name: str) -> bool:
        if self.is_builtin(name):
            raise ValueError(f"Cannot unregister built-in property: {name}")
        with self._lock:
            return self._properties.pop(name, None) is not None

    def clear_custom_properties(self) -> None:
        with self._lock:
            for name in list(self._properties):
                if not self.is_builtin(name):
                    del self._properties[name]

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            items = list(self._properties.items())
        return {
            name: {
                "data_type": prop_def.data_type.__name__,
                "is_per_atom": prop_def.is_per_atom,
                "dimensions": prop_def.dimensions,
                "description": prop_def.description,
                "units": prop_def.units,
                "required": prop_def.required,
                "is_builtin": self.is_builtin(name),
            }
            for name, prop_def in items
        }

    def describe_property(self, name: str) -> str:
        prop_def = self.get(name)
        if prop_def is None:
            return f"Property '{name}' not found"
        return prop_def.describe()

    def validate_property_value(
        self, name: str, value: Any, num_atoms: Optional[int] = None
    ) -> Tuple[bool, str]:
        prop_def = self.get(name)
        if prop_def is None:
            return False, f"Property '{name}' not found"
        return prop_def.validate_value(value, num_atoms)


DEFAULT_REGISTRY = PropertyRegistry.with_builtins()


def create_default_registry() -> PropertyRegistry:
    """Return an isolated copy of ``DEFAULT_REGISTRY``."""
    return DEFAULT_REGISTRY.copy()
