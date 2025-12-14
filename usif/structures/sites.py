#!/usr/bin/env python3
"""
USIF Structure Sites Module

This module provides site representations for different storage modes in USIF:
Wyckoff sites for symmetric crystal storage, Point Group sites for symmetric
molecular storage, and Atom sites for explicit atomic representation.

Main Classes:
    WyckoffSite: Symmetric site for crystals (periodic structures)
    PointGroupSite: Symmetric site for molecules (non-periodic)
    AtomSite: Explicit atomic site with properties

Site Types:
    - WyckoffSite: For CRYSTAL + SYMMETRIC mode
        - Stores atomic number, multiplicity, fractional coordinates, occupancy
        - Used for periodic structures with symmetry

    - PointGroupSite: For MOLECULE + SYMMETRIC mode
        - Stores atomic number, multiplicity, Cartesian coordinates, occupancy
        - Used for molecular structures with point group symmetry

    - AtomSite: For FULL_ATOMIC mode (both crystals and molecules)
        - Stores atomic number, coordinates, and atomic properties
        - Supports per-atom properties (forces, charges, etc.)

Usage:
    >>> from usif.structures.sites import WyckoffSite, PointGroupSite, AtomSite
    >>> from usif import AtomicProperties
    >>>
    >>> # Wyckoff site for crystal
    >>> wyckoff = WyckoffSite(
    ...     atomic_number=14,
    ...     multiplicity=8,
    ...     coords=(0.0, 0.0, 0.0),
    ...     occupancy=1.0
    ... )
    >>>
    >>> # Point group site for molecule
    >>> pg_site = PointGroupSite(
    ...     atomic_number=8,
    ...     multiplicity=2,
    ...     coords=(0.0, 0.0, 0.76),
    ...     occupancy=1.0
    ... )
    >>>
    >>> # Atom site with properties
    >>> atom_props = AtomicProperties(force=(0.1, 0.2, 0.3), charge=0.5)
    >>> atom_site = AtomSite(
    ...     atomic_number=14,
    ...     coords=(0.0, 0.0, 0.0),
    ...     properties=atom_props
    ... )

See Also:
    - USIFStructure: Uses these site types
    - AtomicProperties: Properties for AtomSite
    - StructureType, StorageMode: Structure classification
"""

from dataclasses import dataclass, field
from typing import Tuple

from usif.constants import SymmetryConstants
from usif.properties.atomic import AtomicProperties


@dataclass
class WyckoffSite:
    """Wyckoff position for symmetric storage (periodic only)"""

    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Fractional
    occupancy: float = 1.0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WyckoffSite):
            return False
        return (
            self.atomic_number == other.atomic_number
            and self.multiplicity == other.multiplicity
            and all(
                abs(a - b) < SymmetryConstants.COORDINATE_TOLERANCE
                for a, b in zip(self.coords, other.coords)
            )
            and abs(self.occupancy - other.occupancy)
            < SymmetryConstants.PROPERTY_VALUE_TOLERANCE
        )


@dataclass
@dataclass
class PointGroupSite:
    """Point group symmetric position for molecules"""

    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Cartesian (Å)
    occupancy: float = 1.0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PointGroupSite):
            return False
        return (
            self.atomic_number == other.atomic_number
            and self.multiplicity == other.multiplicity
            and all(
                abs(a - b) < SymmetryConstants.COORDINATE_TOLERANCE
                for a, b in zip(self.coords, other.coords)
            )
            and abs(self.occupancy - other.occupancy)
            < SymmetryConstants.PROPERTY_VALUE_TOLERANCE
        )


@dataclass
class AtomSite:
    """Universal atom site"""

    atomic_number: int
    coords: Tuple[float, float, float]
    properties: AtomicProperties = field(default_factory=AtomicProperties)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AtomSite):
            return False
        return (
            self.atomic_number == other.atomic_number
            and all(
                abs(a - b) < SymmetryConstants.COORDINATE_TOLERANCE
                for a, b in zip(self.coords, other.coords)
            )
            and self.properties == other.properties
        )
