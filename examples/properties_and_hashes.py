#!/usr/bin/env python3
"""Show per-atom properties and geometry/record hash semantics."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from usif import AtomicProperties, AtomSite, StorageMode, StructureProperties, StructureType, USIF, USIFStructure

def main() -> None:
    atom = AtomSite(3, (0, 0, 0), AtomicProperties(force=(0, 0, 0)))
    relaxed = USIFStructure(StructureType.CRYSTAL, StorageMode.FULL_ATOMIC, np.eye(3) * 3.0, atom_sites=[atom], structure_properties=StructureProperties(energy=-1.0), formula="Li")
    excited = USIFStructure(StructureType.CRYSTAL, StorageMode.FULL_ATOMIC, np.eye(3) * 3.0, atom_sites=[atom], structure_properties=StructureProperties(energy=-0.5), formula="Li")
    codec = USIF()
    print(f"Per-atom force: {relaxed.atom_sites[0].properties.force}")
    print(f"Same geometry hash: {codec.get_geometry_hash(relaxed) == codec.get_geometry_hash(excited)}")
    print(f"Same record hash: {codec.get_record_hash(relaxed) == codec.get_record_hash(excited)}")
    print(f"Record hash: {codec.get_record_hash(relaxed)[:16]}...")

if __name__ == "__main__":
    main()
