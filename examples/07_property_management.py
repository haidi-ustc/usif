#!/usr/bin/env python3
"""Manage scalar, vector, tensor, and custom properties on a USIF structure."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usif import AtomicProperties, AtomSite, StorageMode, StructureProperties, StructureType, USIFStructure  # noqa: E402
from usif.services import load_structure, save_structure  # noqa: E402


def build_structure() -> USIFStructure:
    structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3) * 5.0,
        atom_sites=[
            AtomSite(11, (0.0, 0.0, 0.0), AtomicProperties()),
            AtomSite(17, (0.5, 0.5, 0.5), AtomicProperties()),
        ],
        structure_properties=StructureProperties(),
        formula="NaCl",
    )

    # Structure-level built-ins and custom values.
    structure.set_structure_property("energy", -10.5)
    structure.structure_properties.set_tensor("stress", np.eye(3) * 0.1)
    structure.structure_properties.set_vector("dipole", [0.0, 0.0, 1.2])
    structure.structure_properties.set_tensor("elastic_tensor", np.zeros((3, 3, 3, 3)))
    structure.structure_properties.set_custom(
        "calculation", {"code": "example", "converged": True, "kpoints": [4, 4, 4]}
    )

    # Atom-level built-ins and custom values.
    structure.set_atomic_property("charge", [1.0, -1.0])
    structure.set_atomic_property("force", [[0.01, 0.0, 0.0], [-0.01, 0.0, 0.0]])
    structure.set_atom_property(0, "site_tensor", np.eye(2))
    structure.set_atom_property(1, "site_label", "Cl1")
    return structure


def main() -> None:
    structure = build_structure()
    output = Path("property_management.usif.json")
    save_structure(structure, output)
    loaded = load_structure(output)

    print("Energy:", loaded.get_structure_property("energy"))
    print("Stress matrix:", loaded.structure_properties.stress_matrix())
    print("Charges:", loaded.get_atomic_property("charge"))
    print("Atom 1 custom label:", loaded.get_atom_property(1, "site_label"))
    output.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
