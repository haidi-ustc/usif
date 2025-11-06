#!/usr/bin/env python3
"""
USIF Structure Sites
Site representations for Wyckoff, Point Group, and Atomic positions
"""

from typing import Optional, Tuple
from dataclasses import dataclass, field

from usif.properties.atomic import AtomicProperties

@dataclass
class WyckoffSite:
    """Wyckoff position for symmetric storage (periodic only)"""
    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Fractional
    occupancy: float = 1.0
    
    def __eq__(self, other):
        if not isinstance(other, WyckoffSite):
            return False
        return (self.atomic_number == other.atomic_number and
                self.multiplicity == other.multiplicity and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                abs(self.occupancy - other.occupancy) < 1e-6)


@dataclass


@dataclass
class PointGroupSite:
    """Point group symmetric position for molecules"""
    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Cartesian (Å)
    occupancy: float = 1.0
    
    def __eq__(self, other):
        if not isinstance(other, PointGroupSite):
            return False
        return (self.atomic_number == other.atomic_number and
                self.multiplicity == other.multiplicity and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                abs(self.occupancy - other.occupancy) < 1e-6)





@dataclass
class AtomSite:
    """Universal atom site"""
    atomic_number: int
    coords: Tuple[float, float, float]
    properties: AtomicProperties = field(default_factory=AtomicProperties)
    
    def __eq__(self, other):
        if not isinstance(other, AtomSite):
            return False
        return (self.atomic_number == other.atomic_number and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                self.properties == other.properties)


