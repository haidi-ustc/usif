#!/usr/bin/env python3
"""Store structure and atomic properties with canonical unit metadata.

USIF normalizes Unicode and ASCII unit aliases.  For example, ``Å²``,
``Å^2``, ``Ang^2``, and ``angstrom^2`` are all stored as ``Å^2``.  Property
setters store unit metadata but do not convert numeric values.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usif import AtomicProperties, AtomSite, StorageMode, StructureProperties, StructureType, USIFStructure, Units  # noqa: E402
from usif.services import load_structure, save_structure  # noqa: E402


def build_structure() -> USIFStructure:
    props = StructureProperties()
    props.set_scalar("energy", -10.5, units="eV")
    props.set_tensor("stress", np.eye(3) * 0.2, units="GPa")
    props.set_vector("dipole", [0.0, 0.0, 1.2], units="Debye")
    props.set_tensor("quadrupole", np.eye(3), units="Ang^2")
    props.set_custom(
        "calculation",
        {"code": "example", "cutoff": {"value": 520, "units": "eV"}},
        units="dimensionless",
    )

    atom = AtomicProperties()
    atom.set_scalar("charge", -0.25, units="e")
    atom.set_vector("force", [0.1, 0.0, 0.0], units="eV/Ang")
    atom.set_tensor("quadrupole", np.eye(3), units="e Ang^2")

    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3),
        atom_sites=[AtomSite(1, (0.0, 0.0, 0.0), atom)],
        structure_properties=props,
        formula="H",
    )


def main() -> None:
    structure = build_structure()
    output = Path("property_units.usif.json")
    save_structure(structure, output)
    loaded = load_structure(output)

    print("Angstrom alias:", Units.normalize_unit("Ang^2"))
    print("Energy units:", loaded.structure_properties.get_units("energy"))
    print("Quadrupole units:", loaded.structure_properties.get_units("quadrupole"))
    print("Force units:", loaded.atom_sites[0].properties.get_units("force"))
    output.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
