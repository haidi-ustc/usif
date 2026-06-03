"""Hashing helpers for USIF structures."""

import hashlib
import struct

import numpy as np

from usif.constants import BinaryFormat, StorageMode
from usif.structures.structure import USIFStructure


def calculate_structure_hash(structure: USIFStructure) -> bytes:
    """Calculate the SHA-256 hash used by USIF headers and container indexes."""
    data = bytearray()
    data.extend(struct.pack(BinaryFormat.UINT8, structure.structure_type.value))
    data.extend(struct.pack(BinaryFormat.UINT8, structure.storage_mode.value))

    if structure.is_crystal():
        lattice_data = structure.lattice_matrix.astype(np.float32).tobytes()
        data.extend(lattice_data)
        data.extend(struct.pack(BinaryFormat.UINT16, structure.spacegroup))
    elif structure.is_molecular() and structure.storage_mode == StorageMode.SYMMETRIC:
        pg_bytes = (structure.point_group or "C1").encode("utf-8")
        data.extend(struct.pack(BinaryFormat.UINT8, len(pg_bytes)))
        data.extend(pg_bytes)

    if structure.storage_mode == StorageMode.SYMMETRIC:
        sites = (
            structure.wyckoff_sites
            if structure.is_crystal()
            else structure.point_group_sites
        )
        data.extend(struct.pack(BinaryFormat.UINT8, len(sites)))
        for site in sites:
            data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
            data.extend(struct.pack(BinaryFormat.UINT16, site.multiplicity))
            data.extend(
                struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *site.coords)
            )
            data.extend(struct.pack(BinaryFormat.FLOAT32, site.occupancy))
    else:
        data.extend(struct.pack(BinaryFormat.UINT32, len(structure.atom_sites)))
        for site in structure.atom_sites:
            data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
            data.extend(
                struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *site.coords)
            )

    return hashlib.sha256(bytes(data)).digest()
