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


@dataclass
class StructureProperties:
    """Properties that can be attached to the entire structure"""
    energy: Optional[float] = None
    stress: Optional[Tuple[float, ...]] = None
    volume: Optional[float] = None
    pressure: Optional[float] = None
    temperature: Optional[float] = None
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def get_all_properties(self) -> Dict[str, Any]:
        """Get all properties as dictionary"""
        props = {}
        if self.energy is not None:
            props['energy'] = self.energy
        if self.stress is not None:
            props['stress'] = self.stress
        if self.volume is not None:
            props['volume'] = self.volume
        if self.pressure is not None:
            props['pressure'] = self.pressure
        if self.temperature is not None:
            props['temperature'] = self.temperature
        props.update(self.custom)
        return props
    
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StructureProperties):
            return False
        
        def compare_values(v1, v2):
            if v1 is None and v2 is None:
                return True
            if v1 is None or v2 is None:
                return False
            
            # Handle numpy arrays and tuples
            if isinstance(v1, (tuple, list, np.ndarray)) and isinstance(v2, (tuple, list, np.ndarray)):
                if len(v1) != len(v2):
                    return False
                return all(abs(float(a) - float(b)) < 1e-5 for a, b in zip(v1, v2))
            elif isinstance(v1, float) and isinstance(v2, float):
                return abs(v1 - v2) < 1e-5
            else:
                return v1 == v2
        
        for prop_name in ['energy', 'volume', 'pressure', 'temperature']:
            v1 = getattr(self, prop_name, None)
            v2 = getattr(other, prop_name, None)
            if not compare_values(v1, v2):
                return False
        
        # Special handling for stress
        if not compare_values(self.stress, other.stress):
            return False
        
        if self.custom != other.custom:
            return False
        
        return True


