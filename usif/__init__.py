#!/usr/bin/env python3
"""
USIF (Universal Structure Interchange Format) v4.0
Unified format for crystals and molecules with intelligent compression

This module provides a modular structure for the USIF format.
All classes and functions are available at the top level for backward compatibility.

Main Components:
    - USIFStructure: Core structure representation for crystals and molecules
    - USIF: Encoder/decoder for binary USIF format
    - StructureConverter: Convert between USIF and pymatgen formats
    - StructureContainer: HDF5-like container for multiple structures
    - PropertySystem: Type-safe properties with units and validation

Quick Start:
    >>> from usif import USIFStructure, StructureType, StorageMode
    >>> from usif.structures.sites import WyckoffSite
    >>> import numpy as np
    >>>
    >>> # Create a crystal structure
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
    >>> # Save to file
    >>> structure.save('structure.usif')
    >>>
    >>> # Load from file
    >>> loaded = USIFStructure.load('structure.usif')

For more examples, see the examples/ directory.
"""

# Core constants and enums
from .constants import BinaryFormat
from .container import StructureContainer, USIFGroup
from .converter import StructureConverter

# Core functionality
from .encoder import USIF
from .enums import CompressionType, StorageMode, StructureType
from .exceptions import (
    CorruptedDataError,
    DecodingError,
    EncodingError,
    StorageError,
    SymmetryAnalysisError,
    USIFError,
    ValidationError,
)

# Property system
from .properties import (
    AtomicProperties,
    PropertyDefinition,
    PropertyRegistry,
    PropertySerializer,
    StructureProperties,
)

# Structure system
from .structures import (
    AtomSite,
    PointGroupSite,
    USIFStructure,
    WyckoffSite,
)
from .units import UnitConversions, Units

# Utilities
from .utils import (
    USIFBenchmark,
    USIFOptimizer,
)

# Version info - import from version module
from .version import FORMAT_VERSION, VERSION_INFO, __version__

__author__ = "haidi@hfut.edu.cn"

# Export all public API
__all__ = [
    # Constants
    'BinaryFormat',

    # Exceptions
    'USIFError',
    'EncodingError',
    'DecodingError',
    'ValidationError',
    'CorruptedDataError',
    'SymmetryAnalysisError',
    'StorageError',

    # Enums
    'StructureType',
    'StorageMode',
    'CompressionType',

    # Units
    'Units',
    'UnitConversions',

    # Properties
    'PropertyDefinition',
    'PropertySerializer',
    'PropertyRegistry',
    'AtomicProperties',
    'StructureProperties',

    # Structures
    'WyckoffSite',
    'PointGroupSite',
    'AtomSite',
    'USIFStructure',

    # Core
    'USIF',
    'StructureConverter',
    'StructureContainer',
    'USIFGroup',

    # Utils
    'USIFOptimizer',
    'USIFBenchmark',

    # Metadata
    '__version__',
    'FORMAT_VERSION',
    'VERSION_INFO',
    '__author__',
]
