#!/usr/bin/env python3
"""Convert pymatgen -> USIF -> pymatgen using the canonical service/adapter APIs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymatgen.core import Lattice, Structure  # noqa: E402

from usif.interop.pymatgen import PymatgenExporter, SymmetryPolicy  # noqa: E402
from usif.services import export_structure, import_structure  # noqa: E402


def main() -> None:
    source = Structure(
        Lattice.cubic(5.64),
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )
    policy = SymmetryPolicy(mode="analyze")
    usif_structure = import_structure(source, energy=-10.5, symmetry_policy=policy)

    via_adapter = PymatgenExporter.to_pymatgen(usif_structure)
    via_service = export_structure(usif_structure, fmt="pymatgen")

    print(f"pymatgen formula: {via_adapter.composition.reduced_formula}")
    print(f"service formula: {via_service.composition.reduced_formula}")
    print(f"USIF storage mode: {usif_structure.storage_mode.name}")


if __name__ == "__main__":
    main()
