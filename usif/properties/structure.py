#!/usr/bin/env python3
"""
USIF Structure Properties
Properties attached to entire structures
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

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
    
    
    def __eq__(self, other):
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
                return all(abs(float(a) - float(b)) < 1e-6 for a, b in zip(v1, v2))
            elif isinstance(v1, float) and isinstance(v2, float):
                return abs(v1 - v2) < 1e-6
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


