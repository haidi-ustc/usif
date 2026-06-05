#!/usr/bin/env python3
"""USIF (Universal Structure Interchange Format).

Canonical imports are organized by package: structures, storage, interop,
properties, and format.  Top-level exports are intentionally limited to the
lightweight core types.
"""

from .constants import BinaryFormat, CompressionType, StorageMode, StructureType
from .encoder import USIF
from .exceptions import (
    ContainerError,
    ContainerIndexError,
    CorruptedDataError,
    DecodingError,
    EncodingError,
    IntegrityError,
    StorageError,
    SymmetryAnalysisError,
    USIFError,
    ValidationError,
)
from .properties import (
    AtomicProperties,
    DEFAULT_REGISTRY,
    PropertyDefinition,
    PropertyRegistry,
    PropertySerializer,
    StructureProperties,
    create_default_registry,
)
from .structures import (
    SYMMETRY_METADATA_KEY,
    AtomSite,
    PointGroupSite,
    SymmetryMetadata,
    USIFStructure,
    WyckoffSite,
)
from .units import UnitConversions, Units
from .version import FORMAT_VERSION, RELEASE_DATE, RELEASE_ID, RELEASE_RECORD, VERSION_INFO, __version__

__author__ = "haidi@hfut.edu.cn"

__all__ = [
    "BinaryFormat",
    "USIFError",
    "EncodingError",
    "DecodingError",
    "ValidationError",
    "CorruptedDataError",
    "IntegrityError",
    "ContainerError",
    "ContainerIndexError",
    "SymmetryAnalysisError",
    "StorageError",
    "StructureType",
    "StorageMode",
    "CompressionType",
    "Units",
    "UnitConversions",
    "PropertyDefinition",
    "PropertySerializer",
    "PropertyRegistry",
    "DEFAULT_REGISTRY",
    "create_default_registry",
    "AtomicProperties",
    "StructureProperties",
    "WyckoffSite",
    "PointGroupSite",
    "AtomSite",
    "SymmetryMetadata",
    "SYMMETRY_METADATA_KEY",
    "USIFStructure",
    "USIF",
    "__version__",
    "FORMAT_VERSION",
    "VERSION_INFO",
    "RELEASE_DATE",
    "RELEASE_RECORD",
    "RELEASE_ID",
    "__author__",
]
