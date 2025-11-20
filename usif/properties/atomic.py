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
