#!/usr/bin/env python3
"""Demonstrate the official USIF CLI entry point from Python.

This example calls ``usif.cli.main`` directly so the example smoke test does not
need an installed console script.  In a shell, the same operations are available
as ``usif version``, ``usif inspect ...``, and ``usif convert ...``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usif import StorageMode, StructureProperties, StructureType, USIFStructure, WyckoffSite  # noqa: E402
from usif.cli import main as cli_main  # noqa: E402
from usif.services import save_structure  # noqa: E402


def build_structure() -> USIFStructure:
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 5.64,
        spacegroup=225,
        wyckoff_sites=[
            WyckoffSite(atomic_number=11, multiplicity=4, coords=(0.0, 0.0, 0.0)),
            WyckoffSite(atomic_number=17, multiplicity=4, coords=(0.5, 0.5, 0.5)),
        ],
        structure_properties=StructureProperties(energy=-10.5),
        formula="NaCl",
    )


def main() -> None:
    with TemporaryDirectory() as tmp:
        usif_path = Path(tmp) / "nacl.usif"
        json_path = Path(tmp) / "nacl.usif.json"
        save_structure(build_structure(), usif_path)

        print("CLI version:")
        assert cli_main(["version"]) == 0
        assert cli_main(["convert", str(usif_path), str(json_path)]) == 0
        assert cli_main(["inspect", str(json_path)]) == 0
        assert cli_main(["validate", str(json_path)]) == 0
        print("CLI workflow completed")


if __name__ == "__main__":
    main()
