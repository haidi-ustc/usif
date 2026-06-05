#!/usr/bin/env python3
"""Save a USIFStructure as official JSON and load it back."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usif import (  # noqa: E402
    AtomicProperties,
    AtomSite,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
)
from usif.services import load_structure, save_structure, structure_to_json_dict  # noqa: E402


def build_diamond_like_carbon() -> USIFStructure:
    """Build a small full-atomic crystal with JSON-compatible metadata."""
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3) * 3.57,
        atom_sites=[
            AtomSite(6, (0.0, 0.0, 0.0), AtomicProperties(force=(0.0, 0.0, 0.0))),
            AtomSite(6, (0.25, 0.25, 0.25), AtomicProperties(charge=-0.1)),
        ],
        structure_properties=StructureProperties(
            energy=-7.25,
            stress=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            custom={
                "calculator": "example",
                "relaxed": True,
                "labels": ["json", "full-atomic"],
                "notes": {"source": "06_json_structure_roundtrip.py"},
            },
        ),
        formula="C2",
    )


def main() -> None:
    structure = build_diamond_like_carbon()
    payload = structure_to_json_dict(structure)

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "diamond_like_carbon.usif.json"
        save_structure(structure, path)
        loaded = load_structure(path)

        print(f"JSON schema: {payload['@schema']}")
        print(f"JSON formula: {loaded.formula}")
        print(f"JSON custom relaxed: {loaded.structure_properties.custom['relaxed']}")
        print(f"JSON top-level keys: {', '.join(sorted(json.loads(path.read_text()).keys()))}")


if __name__ == "__main__":
    main()
