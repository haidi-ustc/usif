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
from .exceptions import (
    USIFError,
    EncodingError,
    DecodingError,
    ValidationError,
    CorruptedDataError,
    SymmetryAnalysisError,
    StorageError,
)
from .enums import StructureType, StorageMode, CompressionType
from .units import Units, UnitConversions

# Property system
from .properties import (
    PropertyDefinition,
    PropertySerializer,
    PropertyRegistry,
    AtomicProperties,
    StructureProperties,
)

# Structure system
from .structures import (
    WyckoffSite,
    PointGroupSite,
    AtomSite,
    USIFStructure,
)

# Core functionality
from .encoder import USIF
from .converter import StructureConverter
from .container import StructureContainer, USIFGroup

# Utilities
from .utils import (
    USIFOptimizer,
    USIFBenchmark,
)

# Version info
__version__ = "4.0"
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
    '__author__',
]

