"""High-level property management API tests."""

from __future__ import annotations

import numpy as np

from usif import AtomicProperties, AtomSite, StorageMode, StructureProperties, StructureType, USIF, USIFStructure
from usif.services import load_structure_json, save_structure_json


def make_structure() -> USIFStructure:
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3),
        atom_sites=[
            AtomSite(1, (0.0, 0.0, 0.0), AtomicProperties()),
            AtomSite(8, (0.5, 0.5, 0.5), AtomicProperties()),
        ],
        structure_properties=StructureProperties(),
        formula="HO",
    )


def test_structure_properties_manage_scalars_vectors_tensors_and_custom() -> None:
    props = StructureProperties()

    props.set_scalar("energy", np.float64(-10.5))
    props.set_tensor("stress", np.eye(3) * 2.0)
    props.set_vector("dipole", [0.1, 0.2, 0.3])
    props.set_tensor("elastic_tensor", np.zeros((3, 3, 3)))
    props.set_custom("metadata", {"labels": ("relaxed", "checked"), "ok": True})

    assert props.get("energy") == -10.5
    assert props.stress == (2.0, 2.0, 2.0, 0.0, 0.0, 0.0)
    assert props.stress_matrix() == [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]]
    assert props.get_custom("dipole") == [0.1, 0.2, 0.3]
    assert props.get_custom("elastic_tensor")[0][0][0] == 0.0
    assert props.get_custom("metadata") == {"labels": ["relaxed", "checked"], "ok": True}

    assert props.remove("energy") == -10.5
    assert not props.has("energy")


def test_atomic_properties_manage_builtin_and_custom_shapes() -> None:
    props = AtomicProperties()

    props.set_scalar("charge", np.float64(-0.25))
    props.set_vector("force", np.array([1.0, 2.0, 3.0]))
    props.set_tensor("quadrupole", np.eye(3), shape=(3, 3))
    props.set_custom("label", "O1")

    assert props.get("charge") == -0.25
    assert props.get("force") == (1.0, 2.0, 3.0)
    assert props.get_custom("quadrupole") == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert props.get_custom("label") == "O1"


def test_structure_bulk_atomic_property_management() -> None:
    structure = make_structure()

    structure.set_structure_property("energy", -1.23)
    structure.set_atomic_property("charge", [-0.1, 0.1])
    structure.set_atomic_property("force", [[1, 0, 0], [0, 1, 0]])
    structure.set_atom_property(0, "site_tensor", np.eye(2))

    assert structure.get_structure_property("energy") == -1.23
    assert structure.get_atomic_property("charge") == [-0.1, 0.1]
    assert structure.get_atom_property(1, "force") == (0.0, 1.0, 0.0)
    assert structure.get_atom_property(0, "site_tensor") == [[1.0, 0.0], [0.0, 1.0]]


def test_property_management_roundtrips_through_json_and_binary(tmp_path) -> None:
    structure = make_structure()
    structure.set_structure_property("energy", -2.5)
    structure.structure_properties.set_tensor("stress", np.eye(3))
    structure.structure_properties.set_tensor("elastic_tensor", np.ones((2, 2, 2)))
    structure.set_atomic_property("force", [[1, 2, 3], [4, 5, 6]])
    structure.set_atom_property(1, "custom_tensor", np.eye(2))

    json_path = tmp_path / "managed.usif.json"
    save_structure_json(structure, json_path)
    loaded_json = load_structure_json(json_path)

    assert loaded_json.structure_properties.stress == (1.0, 1.0, 1.0, 0.0, 0.0, 0.0)
    assert loaded_json.structure_properties.custom["elastic_tensor"][0][0][0] == 1.0
    assert loaded_json.get_atom_property(1, "custom_tensor") == [[1.0, 0.0], [0.0, 1.0]]

    codec = USIF()
    loaded_binary = codec.decode(codec.encode(structure))[0]
    assert loaded_binary.structure_properties.custom["elastic_tensor"][0][0][0] == 1.0
    assert loaded_binary.get_atom_property(0, "force") == (1.0, 2.0, 3.0)
    assert loaded_binary.get_atom_property(1, "custom_tensor") == [[1.0, 0.0], [0.0, 1.0]]
