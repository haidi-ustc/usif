#!/usr/bin/env python3
"""
USIF Structures Module

This module provides the core structure representation system for USIF,
including sites (Wyckoff, Point Group, Atomic) and the main USIFStructure class.

Main Classes:
    USIFStructure: Main structure representation (crystals and molecules)
    WyckoffSite: Symmetric site for crystals (periodic structures)
    PointGroupSite: Symmetric site for molecules (non-periodic)
    AtomSite: Explicit atomic site representation

Structure Types:
    - CRYSTAL: Periodic structures with lattice
    - MOLECULE: Non-periodic molecular structures

Storage Modes:
    - SYMMETRIC: Store only unique sites with multiplicities (compact)
    - FULL_ATOMIC: Store all atoms explicitly (supports per-atom properties)

Usage:
    >>> from usif import USIFStructure, StructureType, StorageMode
    >>> from usif.structures.sites import WyckoffSite
    >>> import numpy as np
    >>>
    >>> # Create crystal structure
    >>> lattice = np.array([[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]])
    >>> sites = [WyckoffSite(atomic_number=14, multiplicity=8, coords=(0.0, 0.0, 0.0))]
    >>> structure = USIFStructure(
    ...     structure_type=StructureType.CRYSTAL,
    ...     storage_mode=StorageMode.SYMMETRIC,
    ...     lattice_matrix=lattice,
    ...     spacegroup=227,
    ...     wyckoff_sites=sites,
    ...     formula='Si'
    ... )
    >>>
    >>> # Check structure type
    >>> structure.is_crystal()  # True
    >>> structure.is_symmetric()  # True
    >>> structure.num_atoms()  # 8

See Also:
    - usif.interop: optional matsimpy, pymatgen and ASE adapters
    - PropertySystem: Attach properties to structures
"""

from .metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
from .sites import AtomSite, PointGroupSite, WyckoffSite
from .structure import USIFStructure

__all__ = [
    "WyckoffSite",
    "PointGroupSite",
    "AtomSite",
    "SymmetryMetadata",
    "SYMMETRY_METADATA_KEY",
    "USIFStructure",
]
