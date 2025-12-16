#!/usr/bin/env python3
"""
USIF Constants Module

This module provides constants and enumerations used throughout the USIF format, including
binary format specifications, symmetry analysis parameters, and structure classifications.

Main Classes:
    BinaryFormat: Binary format constants for struct pack/unpack
    SymmetryConstants: Constants for symmetry analysis and structure optimization

Main Enumerations:
    StructureType: Type of structure (CRYSTAL or MOLECULE)
    StorageMode: Storage mode (SYMMETRIC or FULL_ATOMIC)
    CompressionType: Compression algorithm (NONE or GZIP)

Usage:
    >>> from usif import BinaryFormat, SymmetryConstants, StructureType, StorageMode
    >>>
    >>> # Use binary format constants
    >>> import struct
    >>> data = struct.pack(BinaryFormat.FLOAT32, 3.14)
    >>>
    >>> # Use symmetry constants
    >>> tolerance = SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE
    >>> coord_tolerance = SymmetryConstants.COORDINATE_TOLERANCE
    >>>
    >>> # Use enumerations
    >>> if structure.structure_type == StructureType.CRYSTAL:
    ...     print("This is a crystal")

See Also:
    - PropertySerializer: Uses BinaryFormat for serialization
    - StructureConverter: Uses SymmetryConstants for analysis
    - USIFStructure: Uses StructureType and StorageMode
"""

from enum import IntEnum


class StructureType(IntEnum):
    """Structure type enumeration"""

    CRYSTAL = 0  # Crystal with lattice
    MOLECULE = 1  # Molecule without lattice


class StorageMode(IntEnum):
    """Storage mode enumeration"""

    SYMMETRIC = 0  # Symmetric storage (Wyckoff/point group)
    FULL_ATOMIC = 1  # Full atomic storage


class CompressionType(IntEnum):
    """Compression type enumeration"""

    NONE = 0
    GZIP = 1


class BinaryFormat:
    """Constants for struct pack/unpack format strings with explicit endianness"""

    # Unsigned integers - all explicit little-endian
    UINT8 = "<B"
    UINT16 = "<H"
    UINT32 = "<I"
    UINT64 = "<Q"

    # Signed integers - all explicit little-endian
    INT8 = "<b"
    INT16 = "<h"
    INT32 = "<i"
    INT64 = "<q"

    # Floating point - all explicit little-endian
    FLOAT32 = "<f"
    FLOAT64 = "<d"

    # Boolean
    BOOL = "<?"

    # Special flags
    LONG_COUNT_FLAG = 0xFF  # 255 indicates long format
    NULL_FLAG = 0xFE  # 254 indicates null value
    NAN_FLAG = 0xFD  # 253 indicates NaN value

    # Arrays
    @staticmethod
    def array(fmt: str, count: int) -> str:
        """Create array format string"""
        clean_fmt = fmt.lstrip("@=<>!")
        return f"{count}{clean_fmt}"


class SymmetryConstants:
    """Constants for symmetry analysis and structure optimization"""

    # Default tolerance for symmetry analysis (in Angstroms)
    DEFAULT_SYMMETRY_TOLERANCE: float = 1e-3

    # Tolerance for spacegroup analysis (in Angstroms)
    DEFAULT_SPACEGROUP_TOLERANCE: float = 0.1

    # Tolerance for molecular symmetry equivalence distance (in Angstroms)
    MOLECULAR_EQUIVALENCE_TOLERANCE: float = 0.01

    # Tolerance for coordinate comparison (for equality checks, in Angstroms)
    COORDINATE_TOLERANCE: float = 1e-6
