#!/usr/bin/env python3
"""Create a USIFStructure manually, encode it, decode it, and inspect hashes."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usif import (  # noqa: E402
    CompressionType,
    StructureProperties,
    StructureType,
    StorageMode,
    USIF,
    USIFStructure,
    WyckoffSite,
)


def build_manual_nacl() -> USIFStructure:
    """Build a compact symmetric NaCl example without external structure objects."""
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 5.64,
        spacegroup=225,
        wyckoff_sites=[
            WyckoffSite(atomic_number=11, multiplicity=4, coords=(0.0, 0.0, 0.0)),
            WyckoffSite(atomic_number=17, multiplicity=4, coords=(0.5, 0.5, 0.5)),
        ],
        structure_properties=StructureProperties(
            energy=-10.5,
            custom={"source": "manual-example", "relaxed": True},
        ),
        formula="NaCl",
    )


def main() -> None:
    structure = build_manual_nacl()
    codec = USIF(compression=CompressionType.GZIP)

    encoded = codec.encode(structure)
    decoded, header_geometry_hash = codec.decode(encoded)

    print(f"Manual formula: {decoded.formula}")
    print(f"Manual atom count: {decoded.num_atoms()}")
    print(f"Encoded byte count: {len(encoded)}")
    print(f"Header geometry hash: {header_geometry_hash.hex()[:16]}...")
    print(f"Record hash: {codec.get_record_hash(decoded)[:16]}...")


if __name__ == "__main__":
    main()
