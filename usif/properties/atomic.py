#!/usr/bin/env python3
"""
USIF Atomic Properties
Properties attached to individual atoms
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from usif.constants import SymmetryConstants

@dataclass
class AtomicProperties:
    """Properties that can be attached to individual atoms"""
    force: Optional[Tuple[float, float, float]] = None
    charge: Optional[float] = None
    magmom: Optional[float] = None
    velocity: Optional[Tuple[float, float, float]] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def get_all_properties(self) -> Dict[str, Any]:
        """Get all properties as dictionary"""
        props = {}
        if self.force is not None:
            props['force'] = self.force
        if self.charge is not None:
            props['charge'] = self.charge
        if self.magmom is not None:
            props['magmom'] = self.magmom
        if self.velocity is not None:
            props['velocity'] = self.velocity
        props.update(self.custom)
        return props

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AtomicProperties):
            return False
        
        def compare_tuples(t1, t2):
            if t1 is None and t2 is None:
                return True
            if t1 is None or t2 is None:
                return False
            
            # Handle numpy arrays
            if isinstance(t1, np.ndarray):
                t1 = tuple(t1)
            if isinstance(t2, np.ndarray):
                t2 = tuple(t2)
                
            if hasattr(t1, '__len__') and hasattr(t2, '__len__'):
                if len(t1) != len(t2):
                    return False
                return all(abs(float(a) - float(b)) < SymmetryConstants.COORDINATE_TOLERANCE for a, b in zip(t1, t2))
            else:
                return abs(float(t1) - float(t2)) < SymmetryConstants.COORDINATE_TOLERANCE
        
        if not compare_tuples(self.force, other.force):
            return False
        if not compare_tuples(self.velocity, other.velocity):
            return False
        
        if self.charge is not None and other.charge is not None:
            if abs(float(self.charge) - float(other.charge)) > SymmetryConstants.COORDINATE_TOLERANCE:
                return False
        elif self.charge != other.charge:
            return False
        
        if self.magmom is not None and other.magmom is not None:
            if abs(float(self.magmom) - float(other.magmom)) > SymmetryConstants.COORDINATE_TOLERANCE:
                return False
        elif self.magmom != other.magmom:
            return False
        
        if self.custom != other.custom:
            return False
        
        return True


