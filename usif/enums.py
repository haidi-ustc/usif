#!/usr/bin/env python3
"""
USIF Enumerations Module

This module provides enumeration types for structure classification,
storage modes, and compression algorithms.

Main Enumerations:
    StructureType: Type of structure (CRYSTAL or MOLECULE)
    StorageMode: Storage mode (SYMMETRIC or FULL_ATOMIC)
    CompressionType: Compression algorithm (NONE or GZIP)

Usage:
    >>> from usif import StructureType, StorageMode, CompressionType
    >>> 
    >>> # Use structure type
    >>> if structure.structure_type == StructureType.CRYSTAL:
    ...     print("This is a crystal")
    >>> 
    >>> # Use storage mode
    >>> if structure.storage_mode == StorageMode.SYMMETRIC:
    ...     print("Using symmetric storage")
    >>> 
    >>> # Use compression type
    >>> structure.save('file.usif', compression=CompressionType.GZIP)

See Also:
    - USIFStructure: Uses StructureType and StorageMode
    - USIF: Uses CompressionType
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

