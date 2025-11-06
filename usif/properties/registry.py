#!/usr/bin/env python3
"""
USIF Property Registry
Registry of built-in property definitions
"""

import logging
from typing import Dict, Optional

from usif.properties.definitions import PropertyDefinition

logger = logging.getLogger(__name__)

class PropertyRegistry:
    """Registry of built-in property definitions"""
    
    _properties: Dict[str, PropertyDefinition] = {
        # Atomic properties
        'force': PropertyDefinition('force', tuple, is_per_atom=True, dimensions=(3,),
                                   description='Force on atom', units='eV/Å'),
        'charge': PropertyDefinition('charge', float, is_per_atom=True,
                                    description='Atomic charge', units='e'),
        'magmom': PropertyDefinition('magmom', float, is_per_atom=True,
                                    description='Magnetic moment', units='μB'),
        'velocity': PropertyDefinition('velocity', tuple, is_per_atom=True, dimensions=(3,),
                                      description='Atomic velocity', units='Å/fs'),
        
        # Structure properties
        'energy': PropertyDefinition('energy', float, description='Total energy', units='eV'),
        'stress': PropertyDefinition('stress', tuple, dimensions=(6,),
                                    description='Stress tensor (Voigt)', units='GPa'),
        'volume': PropertyDefinition('volume', float, description='Cell volume', units='Å³'),
        'pressure': PropertyDefinition('pressure', float, description='Pressure', units='GPa'),
        'temperature': PropertyDefinition('temperature', float, description='Temperature', units='K'),
    }
    
    @classmethod
    def register(cls, prop_def: PropertyDefinition) -> None:
        """Register a new property definition"""
        if prop_def.name in cls._properties:
            import logging; logger = logging.getLogger(__name__); logger.warning(f"Overwriting existing property definition: {prop_def.name}")
        cls._properties[prop_def.name] = prop_def
    
    @classmethod
    def get(cls, name: str) -> Optional[PropertyDefinition]:
        """Get property definition by name"""
        return cls._properties.get(name)
    
    @classmethod
    def is_atomic_property(cls, name: str) -> bool:
        """Check if property is per-atom"""
        prop_def = cls.get(name)
        return prop_def.is_per_atom if prop_def else False
    
    @classmethod
    def is_structure_property(cls, name: str) -> bool:
        """Check if property is structure-level"""
        prop_def = cls.get(name)
        return not prop_def.is_per_atom if prop_def else False

