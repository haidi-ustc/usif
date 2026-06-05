#!/usr/bin/env python3
"""Demonstrate lightweight .usifc introspection and indexed queries."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usif import StorageMode, StructureProperties, StructureType, USIFStructure, WyckoffSite  # noqa: E402
from usif.storage import StructureContainer  # noqa: E402


def make_structure(formula: str, energy: float, family: str, x: float) -> USIFStructure:
    props = StructureProperties(energy=energy)
    props.set_vector("dipole", [x, 0.0, 1.0], units="Debye")
    props.set_custom("metadata", {"family": family, "rank": int(abs(energy) * 10)})
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, (x, 0.0, 0.0))],
        structure_properties=props,
        formula=formula,
    )


def main() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "indexed_materials.usifc"
        with StructureContainer(path, mode="w", use_mmap=False) as container:
            container.add(make_structure("H", -1.0, "hydride", 0.0), name="h1", group="/materials/hydrides")
            container.add(make_structure("H", -2.0, "hydride", 0.2), name="h2", group="/materials/hydrides")
            container.add(make_structure("He", -0.1, "noble", 0.4), name="he1", group="/materials/noble")

        with StructureContainer(path, mode="r", use_mmap=False) as container:
            stats = container.stats()
            hydrides = container.query(custom={"metadata.family": "hydride"})
            low_energy = container.query(property_range=("energy", -2.1, -1.5))
            print(f"Indexed records: {stats['records']}")
            print(f"Indexed formulas: {','.join(container.list_formulas())}")
            print(f"Indexed properties include metadata.family: {'metadata.family' in container.list_properties()}")
            print(f"Hydride query count: {len(hydrides)}")
            print(f"Low-energy query count: {len(low_energy)}")


if __name__ == "__main__":
    main()
