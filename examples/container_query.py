#!/usr/bin/env python3
"""Store and query multiple records in a USIF container."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymatgen.core import Lattice, Structure

from usif import USIF, StructureContainer, USIFStructure


def main() -> None:
    pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    low_energy = USIFStructure.from_source(pmg, energy=-10.5)
    high_energy = USIFStructure.from_source(pmg, energy=-10.0)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "materials.usifc"
        with StructureContainer(path, mode="w") as container:
            low_hash = container.add(low_energy, name="nacl-low", group="/crystals")
            high_hash = container.add(high_energy, name="nacl-high", group="/crystals")
            geometry_hash = USIF().get_geometry_hash(low_energy)
            print(f"Record hashes differ: {low_hash != high_hash}")
            print(f"Same geometry records: {len(container.get_by_geometry_hash(geometry_hash))}")
        with StructureContainer(path, mode="r") as container:
            results = container.query(formula="NaCl", energy_range=(-10.6, -10.1))
            energies = sorted(structure.structure_properties.energy for _, structure in results)
            print(f"Query energies: {energies}")
            print(f"Container stats: {container.stats()['total_structures']} structures")


if __name__ == "__main__":
    main()
