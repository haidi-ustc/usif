"""Tests for model/service architecture boundaries."""

import numpy as np

from usif import (
    AtomicProperties,
    AtomSite,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
    WyckoffSite,
)
from usif.services import (
    export_structure,
    import_pymatgen,
    load_structure,
    load_structure_json,
    save_structure,
    save_structure_json,
    structure_to_json_dict,
)


def make_structure():
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 3.0,
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(14, 1, (0.0, 0.0, 0.0))],
        structure_properties=StructureProperties(energy=-1.0),
        formula="Si",
    )


def test_services_save_load_roundtrip(tmp_path):
    structure = make_structure()
    path = tmp_path / "structure.usif"

    save_structure(structure, path)
    loaded = load_structure(path)

    assert loaded == structure



def test_services_save_load_json_roundtrip(tmp_path):
    structure = make_structure()
    structure.structure_properties.custom.update(
        {
            "calculator": "VASP",
            "relaxed": True,
            "tags": ["json", "roundtrip"],
            "metadata": {"rank": 1, "source": None},
        }
    )
    path = tmp_path / "structure.usif.json"

    save_structure(structure, path)
    loaded = load_structure(path)

    assert loaded == structure
    assert loaded.structure_properties.custom["relaxed"] is True
    assert loaded.structure_properties.custom["metadata"]["source"] is None


def test_explicit_json_service_helpers_roundtrip(tmp_path):
    structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3) * 4.0,
        atom_sites=[
            AtomSite(6, (0.0, 0.0, 0.0), AtomicProperties(force=(1.0, 2.0, 3.0))),
            AtomSite(6, (0.5, 0.5, 0.5), AtomicProperties(charge=-0.25)),
        ],
        structure_properties=StructureProperties(
            energy=-2.5,
            stress=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
            custom={"nested": {"ok": True}},
        ),
        formula="C2",
    )
    path = tmp_path / "structure.json"

    payload = structure_to_json_dict(structure)
    assert payload["@schema"] == "usif.structure.json.v1"
    assert isinstance(payload["structure_properties"], dict)

    save_structure_json(structure, path)
    loaded = load_structure_json(path)

    assert loaded == structure
    assert loaded.atom_sites[0].properties.force == (1.0, 2.0, 3.0)


def test_unsupported_service_file_extension_is_rejected(tmp_path):
    structure = make_structure()
    path = tmp_path / "structure.yaml"

    try:
        save_structure(structure, path)
    except Exception as exc:
        assert "Unsupported structure file extension" in str(exc)
    else:
        raise AssertionError("unsupported extension was accepted")


def test_export_service_converts_to_pymatgen():
    structure = make_structure()

    assert export_structure(structure, fmt="pymatgen").composition.reduced_formula == "Si"


def test_export_service_supports_json_filename(tmp_path):
    structure = make_structure()
    path = tmp_path / "exported.json"

    export_structure(structure, filename=path)
    loaded = load_structure(path)

    assert loaded == structure


def test_import_pymatgen_service_roundtrip():
    pmg = export_structure(make_structure(), fmt="pymatgen")

    imported = import_pymatgen(pmg, force_symmetric=True)

    assert imported.formula == "Si"
    assert imported.storage_mode == StorageMode.SYMMETRIC
