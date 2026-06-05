#!/usr/bin/env python3
"""Demonstrate atom properties and the difference between geometry and record hashes."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usif import (  # noqa: E402
    AtomicProperties,
    AtomSite,
    StorageMode,
    StructureProperties,
    StructureType,
    USIF,
    USIFStructure,
)


def lithium_with_energy(energy: float) -> USIFStructure:
    atom = AtomSite(
        atomic_number=3,
        coords=(0.0, 0.0, 0.0),
        properties=AtomicProperties(force=(0.0, 0.0, 0.0), charge=0.0),
    )
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3) * 3.0,
        atom_sites=[atom],
        structure_properties=StructureProperties(energy=energy, custom={"phase": "bcc-like"}),
        formula="Li",
    )


def main() -> None:
    relaxed = lithium_with_energy(-1.0)
    excited = lithium_with_energy(-0.5)
    codec = USIF()

    print(f"Per-atom force: {relaxed.atom_sites[0].properties.force}")
    print(f"Same geometry hash: {codec.get_geometry_hash(relaxed) == codec.get_geometry_hash(excited)}")
    print(f"Same record hash: {codec.get_record_hash(relaxed) == codec.get_record_hash(excited)}")
    print(f"Record hash: {codec.get_record_hash(relaxed)[:16]}...")


if __name__ == "__main__":
    main()
