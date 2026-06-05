"""Unit metadata and unit alias tests for properties."""

from __future__ import annotations

import json

import numpy as np

from usif import AtomicProperties, AtomSite, StorageMode, StructureProperties, StructureType, USIF, USIFStructure, Units


def make_structure() -> USIFStructure:
    props = StructureProperties()
    props.set_scalar("energy", -10.5)
    props.set_tensor("stress", np.eye(3), units="GPa")
    props.set_vector("dipole", [0.0, 0.0, 1.2], units="Debye")
    props.set_tensor("quadrupole", np.eye(3), units="Ang^2")
    props.set_custom("calculation", {"cutoff": {"value": 520, "units": "eV"}})

    atom = AtomicProperties()
    atom.set_scalar("charge", -0.25)
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


def test_unit_aliases_normalize_unicode_and_ascii_spellings() -> None:
    aliases = ["Å²", "Å^2", "Ang^2", "angstrom^2", "angstrom²"]
    assert {Units.normalize_unit(unit) for unit in aliases} == {"Å^2"}
    assert Units.are_compatible("Å²", "Ang^2")
    assert Units.is_valid_unit("Ang^2")
    assert Units.normalize_unit("eV/Ang") == "eV/Å"
    assert Units.normalize_unit("cm⁻¹") == "cm^-1"
    assert Units.normalize_unit("g/cm³") == "g/cm^3"


def test_property_setters_store_canonical_units_and_return_bare_values() -> None:
    props = StructureProperties()
    props.set_scalar("energy", -10.5)
    props.set_vector("dipole", [0, 0, 1.2], units="Debye")
    props.set_tensor("quadrupole", np.eye(3), units="Ang^2")

    assert props.get("energy") == -10.5
    assert props.get_units("energy") == "eV"
    assert props.get_custom("dipole") == [0.0, 0.0, 1.2]
    assert props.get_units("quadrupole") == "Å^2"
    assert props.get_custom_envelope("quadrupole")["units"] == "Å^2"

    atom = AtomicProperties()
    atom.set_vector("force", [1, 2, 3], units="eV/Ang")
    atom.set_tensor("quadrupole", np.eye(3), units="e Ang^2")

    assert atom.get("force") == (1.0, 2.0, 3.0)
    assert atom.get_units("force") == "eV/Å"
    assert atom.get_units("quadrupole") == "e Å^2"


def test_unit_metadata_roundtrips_through_model_json_and_binary() -> None:
    structure = make_structure()

    json_payload = json.loads(json.dumps(structure.as_dict(), ensure_ascii=False))
    from_json = USIFStructure.from_dict(json_payload)
    assert from_json.structure_properties.get_units("dipole") == "Debye"
    assert from_json.structure_properties.get_units("quadrupole") == "Å^2"
    assert from_json.atom_sites[0].properties.get_units("force") == "eV/Å"
    assert from_json.atom_sites[0].properties.get_units("quadrupole") == "e Å^2"

    decoded = USIF().decode(USIF().encode(structure))[0]
    assert decoded.structure_properties.get_units("energy") == "eV"
    assert decoded.structure_properties.get_units("dipole") == "Debye"
    assert decoded.structure_properties.get_units("quadrupole") == "Å^2"
    assert decoded.atom_sites[0].properties.get_units("charge") == "e"
    assert decoded.atom_sites[0].properties.get_units("force") == "eV/Å"
    assert decoded.atom_sites[0].properties.get_units("quadrupole") == "e Å^2"
