#!/usr/bin/env python3
"""Minimal USIF quickstart: arrays -> USIF -> .usif -> USIF (no optional backend needed)."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np  # noqa: E402

from usif.interop.common import build_structure  # noqa: E402
from usif.services import load_structure, save_structure  # noqa: E402


def main() -> None:
    structure = build_structure(
        [11, 17],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
        lattice=np.eye(3) * 5.64,
        cartesian=False,
        energy=-10.5,
        custom={"calculator": "VASP"},
    )
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "nacl.usif"
        save_structure(structure, path)
        loaded = load_structure(path)
    print(f"Formula: {loaded.formula}")
    print(f"Energy: {loaded.structure_properties.energy} eV")
    print(f"Custom calculator: {loaded.structure_properties.custom['calculator']}")


if __name__ == "__main__":
    main()
