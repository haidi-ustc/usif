#!/usr/bin/env python3
"""Legacy example 1: basic binary round trip."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from usif import (
    USIF,
    CompressionType,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
    WyckoffSite,
)


def main() -> None:
    structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 5.64,
        spacegroup=225,
        wyckoff_sites=[WyckoffSite(11, 4, (0, 0, 0)), WyckoffSite(17, 4, (0.5, 0.5, 0.5))],
        structure_properties=StructureProperties(energy=-10.5, custom={"source": "example-1"}),
        formula="NaCl",
    )
    codec = USIF(compression=CompressionType.GZIP)
    data = codec.encode(structure)
    decoded, geometry_hash = codec.decode(data)
    print(f"Formula: {decoded.formula}")
    print(f"Atoms: {decoded.num_atoms()}")
    print(f"Encoded bytes: {len(data)}")
    print(f"Geometry hash: {geometry_hash.hex()[:16]}...")


if __name__ == "__main__":
    main()
