#!/usr/bin/env python3
"""Convert matsimpy -> USIF -> matsimpy.

Needs the optional matsimpy backend (install it from its source checkout).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matsimpy  # noqa: E402

from usif.services import export_structure, import_structure  # noqa: E402


def main() -> None:
    source = matsimpy.Crystal(
        ["Na", "Cl"],
        [[0, 0, 0], [2.82, 2.82, 2.82]],
        matsimpy.Lattice([[5.64, 0, 0], [0, 5.64, 0], [0, 0, 5.64]]),
        coords_are_cartesian=True,
        metadata={"energy": -10.5, "calculator": "example"},
    )
    structure = import_structure(source)
    roundtrip = export_structure(structure, fmt="matsimpy")

    print(f"USIF formula: {structure.formula}")
    print(f"USIF energy: {structure.structure_properties.energy} eV")
    print(f"matsimpy sites: {len(roundtrip.species)}")


if __name__ == "__main__":
    main()
