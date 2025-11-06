#!/usr/bin/env python3
"""
USIF Enumerations
Type enumerations for structure types, storage modes, and compression
"""

from enum import IntEnum


class StructureType(IntEnum):
    """Structure type enumeration"""
    PERIODIC = 0  # Crystal with lattice
    MOLECULAR = 1  # Molecule without lattice


class StorageMode(IntEnum):
    """Storage mode enumeration"""
    SYMMETRIC = 0  # Symmetric storage (Wyckoff/point group)
    FULL_ATOMIC = 1  # Full atomic storage


class CompressionType(IntEnum):
    """Compression type enumeration"""
    NONE = 0
    GZIP = 1

