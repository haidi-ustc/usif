#!/usr/bin/env python3
"""Legacy example 2: container write/read/query workflow."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymatgen.core import Lattice, Structure

from usif import StructureContainer, USIFStructure


def make_structure(formula: str, energy: float):
    if formula == "NaCl":
        pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    else:
        pmg = Structure(Lattice.cubic(3.0), ["Li"], [[0, 0, 0]])
    return USIFStructure.from_source(pmg, energy=energy)


def main() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "structures.usifc"
        with StructureContainer(path, mode="w") as container:
            container.add(make_structure("NaCl", -10.5), name="nacl", group="/examples")
            container.add(make_structure("Li", -1.0), name="li", group="/examples")
            print(f"Written structures: {len(container)}")
        with StructureContainer(path, mode="r") as container:
            print(f"Queried structures: {len(container.query(group='/examples'))}")
            print(f"Names: {sorted(container._name_index.keys())}")


if __name__ == "__main__":
    main()
