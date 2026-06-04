#!/usr/bin/env python3
"""Convert between pymatgen and USIF."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymatgen.core import Lattice, Structure
from usif import StructureConverter, USIFStructure

def main() -> None:
    pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    structure = USIFStructure.from_source(pmg, energy=-10.5)
    round_tripped = StructureConverter.to_pymatgen(structure)
    print(f"pymatgen formula: {round_tripped.composition.reduced_formula}")
    print(f"USIF formula: {structure.formula}")

if __name__ == "__main__":
    main()
