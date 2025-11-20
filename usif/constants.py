#!/usr/bin/env python3
"""
USIF Constants Module

This module provides constants used throughout the USIF format, including
binary format specifications and symmetry analysis parameters.

Main Classes:
    BinaryFormat: Binary format constants for struct pack/unpack
    SymmetryConstants: Constants for symmetry analysis and structure optimization

Usage:
    >>> from usif import BinaryFormat, SymmetryConstants
    >>>
    >>> # Use binary format constants
    >>> import struct
    >>> data = struct.pack(BinaryFormat.FLOAT32, 3.14)
    >>>
    >>> # Use symmetry constants
    >>> tolerance = SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE
    >>> coord_tolerance = SymmetryConstants.COORDINATE_TOLERANCE

See Also:
    - PropertySerializer: Uses BinaryFormat for serialization
    - StructureConverter: Uses SymmetryConstants for analysis
"""


class BinaryFormat:
    """Constants for struct pack/unpack format strings with explicit endianness"""
    # Unsigned integers - all explicit little-endian
    UINT8 = '<B'
    UINT16 = '<H'
    UINT32 = '<I'
    UINT64 = '<Q'

    # Signed integers - all explicit little-endian
    INT8 = '<b'
    INT16 = '<h'
    INT32 = '<i'
    INT64 = '<q'

    # Floating point - all explicit little-endian
    FLOAT32 = '<f'
    FLOAT64 = '<d'

    # Boolean
    BOOL = '<?'

    # Special flags
    LONG_COUNT_FLAG = 0xFF  # 255 indicates long format
    NULL_FLAG = 0xFE        # 254 indicates null value
    NAN_FLAG = 0xFD         # 253 indicates NaN value

    # Arrays
    @staticmethod
    def array(fmt: str, count: int) -> str:
        """Create array format string"""
        clean_fmt = fmt.lstrip('@=<>!')
        return f'{count}{clean_fmt}'


class SymmetryConstants:
    """Constants for symmetry analysis and structure optimization"""

    # Default tolerance for symmetry analysis (in Angstroms)
    DEFAULT_SYMMETRY_TOLERANCE: float = 1e-3

    # Symmetry precision for spacegroup analysis (in Angstroms)
    DEFAULT_SYMMETRY_PRECISION: float = 0.1

    # Distance threshold for molecular symmetry equivalence (in Angstroms)
    MOLECULAR_EQUIVALENCE_THRESHOLD: float = 0.01

    # Property value comparison tolerance (for floating point comparisons)
    PROPERTY_VALUE_TOLERANCE: float = 0.001

    # Coordinate comparison tolerance (for equality checks, in Angstroms)
    COORDINATE_TOLERANCE: float = 1e-6
