#!/usr/bin/env python3
"""Use SymmetryPolicy to choose full-atom or symmetry-aware import behavior."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymatgen.core import Lattice, Structure  # noqa: E402

from usif.interop.pymatgen import SymmetryPolicy  # noqa: E402
from usif.services import import_structure  # noqa: E402


def main() -> None:
    source = Structure(
        Lattice.cubic(5.64),
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )
    analyze = import_structure(source, symmetry_policy=SymmetryPolicy(mode="analyze"))
    full = import_structure(source, symmetry_policy=SymmetryPolicy(mode="none"))

    print(f"Analyze policy mode: {analyze.storage_mode.name}")
    print(f"None policy mode: {full.storage_mode.name}")
    print(f"Formula: {analyze.formula}")


if __name__ == "__main__":
    main()
