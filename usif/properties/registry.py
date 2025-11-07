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
from typing import Dict, Optional

from usif.properties.definitions import PropertyDefinition

logger = logging.getLogger(__name__)

# Import Units here to avoid circular import issues
from usif.units import Units

class PropertyRegistry:
    """Registry of built-in property definitions"""
    
    _properties: Dict[str, PropertyDefinition] = {
        # Atomic properties
        'force': PropertyDefinition('force', tuple, is_per_atom=True, dimensions=(3,),
                                   description='Force on atom', units=Units.EV_PER_ANGSTROM),
        'charge': PropertyDefinition('charge', float, is_per_atom=True,
                                    description='Atomic charge', units=Units.ELEMENTARY_CHARGE),
        'magmom': PropertyDefinition('magmom', float, is_per_atom=True,
                                    description='Magnetic moment', units=Units.BOHR_MAGNETON),
        'velocity': PropertyDefinition('velocity', tuple, is_per_atom=True, dimensions=(3,),
                                      description='Atomic velocity', units=Units.ANGSTROM_PER_FS),
        
        # Structure properties
        'energy': PropertyDefinition('energy', float, description='Total energy', units=Units.EV),
        'stress': PropertyDefinition('stress', tuple, dimensions=(6,),
                                    description='Stress tensor (Voigt)', units=Units.GPA),
        'volume': PropertyDefinition('volume', float, description='Cell volume', units=Units.ANGSTROM_CUBED),
        'pressure': PropertyDefinition('pressure', float, description='Pressure', units=Units.GPA),
        'temperature': PropertyDefinition('temperature', float, description='Temperature', units=Units.KELVIN),
    }
    
    @classmethod
    def register(cls, prop_def: PropertyDefinition) -> None:
        """
        Register a new property definition
        
        Adds a custom property definition to the registry. If a property with
        the same name already exists, it will be overwritten with a warning.
        
        Args:
            prop_def: PropertyDefinition instance to register
            
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
        if prop_def.name in cls._properties:
            import logging; logger = logging.getLogger(__name__); logger.warning(f"Overwriting existing property definition: {prop_def.name}")
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
        return cls._properties.get(name)
    
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
