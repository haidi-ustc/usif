#!/usr/bin/env python3
"""
USIF (Universal Structure Interchange Format) v4.0
Unified format for crystals and molecules with intelligent compression

This module provides a modular structure for the USIF format.
All classes and functions are available at the top level for backward compatibility.
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

