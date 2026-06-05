#!/usr/bin/env python3
"""Minimal USIF quickstart: pymatgen -> USIF -> .usif -> USIF."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymatgen.core import Lattice, Structure

from usif.services import import_structure, load_structure, save_structure


def main() -> None:
    pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    structure = import_structure(pmg, energy=-10.5, calculator="VASP")
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "nacl.usif"
        save_structure(structure, path)
        loaded = load_structure(path)
    print(f"Formula: {loaded.formula}")
    print(f"Energy: {loaded.structure_properties.energy} eV")
    print(f"Custom calculator: {loaded.structure_properties.custom['calculator']}")


if __name__ == "__main__":
    main()
