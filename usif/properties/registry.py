#!/usr/bin/env python3
"""
USIF Property Registry Module

This module provides a registry of built-in property definitions for common
materials science properties. It includes both atomic (per-atom) and structure-level properties.

Main Class:
    PropertyRegistry: Registry of built-in property definitions

Built-in Properties:
    Atomic (per-atom):
        - force: Force vector (eV/Å)
        - charge: Atomic charge (e)
        - magmom: Magnetic moment (μB)
        - velocity: Atomic velocity (Å/fs)

    Structure-level:
        - energy: Total energy (eV)
        - stress: Stress tensor in Voigt notation (GPa)
        - volume: Cell volume (Å³)
        - pressure: Pressure (GPa)
        - temperature: Temperature (K)

Usage:
    >>> from usif import PropertyRegistry
    >>>
    >>> # Get built-in property definition
    >>> energy_def = PropertyRegistry.get('energy')
    >>> force_def = PropertyRegistry.get('force')
    >>>
    >>> # Check property type
    >>> PropertyRegistry.is_atomic_property('force')  # True
    >>> PropertyRegistry.is_structure_property('energy')  # True
    >>>
    >>> # Register custom property
    >>> from usif import PropertyDefinition, Units
    >>> custom_prop = PropertyDefinition(
    ...     name='band_gap',
    ...     data_type=float,
    ...     units=Units.EV,
    ...     description='Electronic band gap'
    ... )
    >>> PropertyRegistry.register(custom_prop)

See Also:
    - PropertyDefinition: Define custom properties
    - PropertySerializer: Serialize property values
    - Units: Physical unit constants
"""

import logging
import threading
from typing import Dict, List, Optional, Any, Tuple

from usif.properties.definitions import PropertyDefinition

logger = logging.getLogger(__name__)


class PropertyRegistry:
    """Registry of built-in and custom property definitions"""

    _lock = threading.RLock()
    _initialized = False
    _properties: Dict[str, PropertyDefinition] = {}
    
    # Built-in properties that cannot be unregistered
    _builtin_properties = {
        "force", "charge", "magmom", "velocity", 
        "energy", "stress", "volume", "pressure", "temperature"
    }

    @classmethod
    def _initialize_builtins(cls) -> None:
        """Initialize built-in properties (lazy loading to avoid circular imports)"""
        from usif.units import Units
        
        builtins = {
            # Atomic properties
            "force": PropertyDefinition(
                "force", tuple, is_per_atom=True, dimensions=(3,),
                description="Force on atom", units=Units.EV_PER_ANGSTROM,
            ),
            "charge": PropertyDefinition(
                "charge", float, is_per_atom=True,
                description="Atomic charge", units=Units.ELEMENTARY_CHARGE,
            ),
            "magmom": PropertyDefinition(
                "magmom", float, is_per_atom=True,
                description="Magnetic moment", units=Units.BOHR_MAGNETON,
            ),
            "velocity": PropertyDefinition(
                "velocity", tuple, is_per_atom=True, dimensions=(3,),
                description="Atomic velocity", units=Units.ANGSTROM_PER_FS,
            ),
            # Structure properties
            "energy": PropertyDefinition(
                "energy", float, description="Total energy", units=Units.EV
            ),
            "stress": PropertyDefinition(
                "stress", tuple, dimensions=(6,),
                description="Stress tensor (Voigt notation)", units=Units.GPA,
            ),
            "volume": PropertyDefinition(
                "volume", float, description="Cell volume", units=Units.ANGSTROM_CUBED
            ),
            "pressure": PropertyDefinition(
                "pressure", float, description="Pressure", units=Units.GPA
            ),
            "temperature": PropertyDefinition(
                "temperature", float, description="Temperature", units=Units.KELVIN
            ),
        }
        
        with cls._lock:
            cls._properties.update(builtins)
            cls._initialized = True

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure registry is initialized"""
        if not cls._initialized:
            cls._initialize_builtins()

    @classmethod
    def register(cls, prop_def: PropertyDefinition) -> None:
        """
        Register a new property definition

        Adds a custom property definition to the registry. If a property with
        the same name already exists, it will be overwritten with a warning.

        Args:
            prop_def: PropertyDefinition instance to register

        Raises:
            TypeError: If prop_def is not a PropertyDefinition
            ValueError: If prop_def has invalid name or conflicts with reserved names

        Example:
            >>> from usif import PropertyDefinition, Units, PropertyRegistry
            >>> custom_prop = PropertyDefinition(
            ...     name="band_gap",
            ...     data_type=float,
            ...     units=Units.EV,
            ...     description="Electronic band gap"
            ... )
            >>> PropertyRegistry.register(custom_prop)
        """
        # Validate input
        if not isinstance(prop_def, PropertyDefinition):
            raise TypeError(f"Expected PropertyDefinition, got {type(prop_def)}")
        
        if not prop_def.name or not isinstance(prop_def.name, str):
            raise ValueError("Property definition must have a valid name")
        
        # Validate name doesn't conflict with reserved names
        reserved_names = {'type', 'name', 'units', 'description', 'id', 'class'}
        if prop_def.name in reserved_names:
            raise ValueError(f"Property name '{prop_def.name}' is reserved")
        
        cls._ensure_initialized()
        
        with cls._lock:
            if prop_def.name in cls._properties:
                if cls.is_builtin(prop_def.name):
                    logger.warning(f"Overwriting built-in property definition: {prop_def.name}")
                else:
                    logger.info(f"Overwriting custom property definition: {prop_def.name}")
            cls._properties[prop_def.name] = prop_def

    @classmethod
    def get(cls, name: str) -> Optional[PropertyDefinition]:
        """
        Get property definition by name

        Retrieves a property definition from the registry, either built-in or
        custom registered property.

        Args:
            name: Property name (e.g., "energy", "force", "charge")

        Returns:
            PropertyDefinition if found, None otherwise

        Example:
            >>> energy_def = PropertyRegistry.get("energy")
            >>> print(f"Energy unit: {energy_def.units}")  # "eV"
        """
        cls._ensure_initialized()
        return cls._properties.get(name)

    @classmethod
    def get_required(cls, name: str) -> PropertyDefinition:
        """
        Get property definition, raise error if not found

        Args:
            name: Property name

        Returns:
            PropertyDefinition instance

        Raises:
            KeyError: If property definition is not found

        Example:
            >>> try:
            ...     prop_def = PropertyRegistry.get_required("energy")
            ... except KeyError:
            ...     print("Property not found")
        """
        cls._ensure_initialized()
        prop_def = cls._properties.get(name)
        if prop_def is None:
            available = list(cls._properties.keys())
            raise KeyError(f"Property '{name}' not found in registry. "
                          f"Available properties: {available}")
        return prop_def

    @classmethod
    def is_atomic_property(cls, name: str) -> bool:
        """
        Check if property is atomic (per-atom)

        Determines whether a property is attached to individual atoms
        (e.g., force, charge) rather than the entire structure.

        Args:
            name: Property name

        Returns:
            bool: True if property is atomic, False otherwise

        Example:
            >>> PropertyRegistry.is_atomic_property("force")  # True
            >>> PropertyRegistry.is_atomic_property("energy")  # False
        """
        prop_def = cls.get(name)
        return prop_def.is_per_atom if prop_def else False

    @classmethod
    def is_structure_property(cls, name: str) -> bool:
        """
        Check if property is structure-level

        Determines whether a property is attached to the entire structure
        (e.g., energy, volume) rather than individual atoms.

        Args:
            name: Property name

        Returns:
            bool: True if property is structure-level, False otherwise

        Example:
            >>> PropertyRegistry.is_structure_property("energy")  # True
            >>> PropertyRegistry.is_structure_property("force")  # False
        """
        prop_def = cls.get(name)
        return not prop_def.is_per_atom if prop_def else False

    @classmethod
    def is_builtin(cls, name: str) -> bool:
        """
        Check if property is a built-in (non-removable) property

        Args:
            name: Property name

        Returns:
            bool: True if property is built-in, False otherwise
        """
        return name in cls._builtin_properties

    @classmethod
    def exists(cls, name: str) -> bool:
        """
        Check if property definition exists

        Args:
            name: Property name

        Returns:
            bool: True if property exists, False otherwise
        """
        cls._ensure_initialized()
        return name in cls._properties

    @classmethod
    def list_properties(cls, atomic_only: bool = False, structure_only: bool = False) -> List[str]:
        """
        List available property names with filtering

        Args:
            atomic_only: If True, only return atomic properties
            structure_only: If True, only return structure properties

        Returns:
            List of property names

        Raises:
            ValueError: If both atomic_only and structure_only are True

        Example:
            >>> # List all properties
            >>> all_props = PropertyRegistry.list_properties()
            >>> 
            >>> # List only atomic properties
            >>> atomic_props = PropertyRegistry.list_properties(atomic_only=True)
            >>> 
            >>> # List only structure properties
            >>> structure_props = PropertyRegistry.list_properties(structure_only=True)
        """
        if atomic_only and structure_only:
            raise ValueError("Cannot specify both atomic_only and structure_only")
        
        cls._ensure_initialized()
        names = list(cls._properties.keys())
        
        if atomic_only:
            return [name for name in names if cls.is_atomic_property(name)]
        elif structure_only:
            return [name for name in names if cls.is_structure_property(name)]
        else:
            return names

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Remove a custom property definition

        Args:
            name: Property name to remove

        Returns:
            bool: True if property was removed, False if it didn't exist

        Raises:
            ValueError: If trying to remove a built-in property

        Example:
            >>> # Register a custom property
            >>> custom_prop = PropertyDefinition("custom", float)
            >>> PropertyRegistry.register(custom_prop)
            >>> 
            >>> # Remove the custom property
            >>> success = PropertyRegistry.unregister("custom")
            >>> print(f"Removed: {success}")  # True
        """
        if cls.is_builtin(name):
            raise ValueError(f"Cannot unregister built-in property: {name}")
        
        cls._ensure_initialized()
        with cls._lock:
            if name in cls._properties:
                del cls._properties[name]
                return True
        return False

    @classmethod
    def clear_custom_properties(cls) -> None:
        """
        Remove all custom property definitions, keeping only built-in properties

        Example:
            >>> # Clear all custom properties
            >>> PropertyRegistry.clear_custom_properties()
        """
        cls._ensure_initialized()
        with cls._lock:
            custom_props = [name for name in cls._properties.keys() if not cls.is_builtin(name)]
            for name in custom_props:
                del cls._properties[name]

    @classmethod
    def to_dict(cls) -> Dict[str, Dict[str, Any]]:
        """
        Serialize registry to dictionary

        Returns:
            Dictionary containing property definitions metadata

        Example:
            >>> registry_dict = PropertyRegistry.to_dict()
            >>> print(registry_dict['energy']['units'])  # 'eV'
        """
        cls._ensure_initialized()
        return {
            name: {
                'data_type': prop_def.data_type.__name__,
                'is_per_atom': prop_def.is_per_atom,
                'dimensions': prop_def.dimensions,
                'description': prop_def.description,
                'units': prop_def.units,
                'required': prop_def.required,
                'is_builtin': cls.is_builtin(name)
            }
            for name, prop_def in cls._properties.items()
        }

    @classmethod
    def describe_property(cls, name: str) -> str:
        """
        Get human-readable description of a property

        Args:
            name: Property name

        Returns:
            String description of the property

        Example:
            >>> desc = PropertyRegistry.describe_property("energy")
            >>> print(desc)
        """
        prop_def = cls.get(name)
        if prop_def is None:
            return f"Property '{name}' not found"
        return prop_def.describe()

    @classmethod
    def validate_property_value(cls, name: str, value: Any, num_atoms: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate a value against a property definition

        Args:
            name: Property name
            value: Value to validate
            num_atoms: Number of atoms (required for per-atom properties)

        Returns:
            Tuple of (is_valid, message)

        Example:
            >>> is_valid, message = PropertyRegistry.validate_property_value("energy", -10.5)
            >>> print(f"Valid: {is_valid}, Message: {message}")
        """
        prop_def = cls.get(name)
        if prop_def is None:
            return False, f"Property '{name}' not found"
        
        return prop_def.validate_value(value, num_atoms)


# Example usage and testing
if __name__ == "__main__":
    # Test the PropertyRegistry class
    print("=== Property Registry Demo ===")
    
    # List all properties
    all_props = PropertyRegistry.list_properties()
    print(f"All properties: {all_props}")
    
    # List atomic properties
    atomic_props = PropertyRegistry.list_properties(atomic_only=True)
    print(f"Atomic properties: {atomic_props}")
    
    # List structure properties
    structure_props = PropertyRegistry.list_properties(structure_only=True)
    print(f"Structure properties: {structure_props}")
    
    # Get property definitions
    energy_def = PropertyRegistry.get("energy")
    force_def = PropertyRegistry.get("force")
    
    print(f"\nEnergy property: {energy_def.describe() if energy_def else 'Not found'}")
    print(f"Force property: {force_def.describe() if force_def else 'Not found'}")
    
    # Check property types
    print(f"\nIs 'force' atomic? {PropertyRegistry.is_atomic_property('force')}")
    print(f"Is 'energy' atomic? {PropertyRegistry.is_atomic_property('energy')}")
    print(f"Is 'energy' structure? {PropertyRegistry.is_structure_property('energy')}")
    
    # Validate values
    print(f"\nValidation tests:")
    print(f"Energy -10.5: {PropertyRegistry.validate_property_value('energy', -10.5)}")
    print(f"Force validation: {PropertyRegistry.validate_property_value('force', ((1.0, 2.0, 3.0),), num_atoms=1)}")
    
    # Test custom property registration
    from usif.properties.definitions import PropertyDefinition
    
    custom_prop = PropertyDefinition(
        name="band_gap",
        data_type=float,
        description="Electronic band gap",
        units="eV"
    )
    
    PropertyRegistry.register(custom_prop)
    print(f"\nCustom property registered: {PropertyRegistry.exists('band_gap')}")
    print(f"Custom property description: {PropertyRegistry.describe_property('band_gap')}")
    
    # Test serialization
    registry_dict = PropertyRegistry.to_dict()
    print(f"\nRegistry has {len(registry_dict)} properties")
    print(f"Energy property metadata: {registry_dict['energy']}")