"""Tests for model/service architecture boundaries."""

import numpy as np

from usif import StorageMode, StructureProperties, StructureType, USIFStructure, WyckoffSite
from usif.services import export_structure, import_pymatgen, load_structure, save_structure


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


def test_export_service_converts_to_pymatgen():
    structure = make_structure()

    assert export_structure(structure, fmt="pymatgen").composition.reduced_formula == "Si"


def test_import_pymatgen_service_roundtrip():
    pmg = export_structure(make_structure(), fmt="pymatgen")

    imported = import_pymatgen(pmg, force_symmetric=True)

    assert imported.formula == "Si"
    assert imported.storage_mode == StorageMode.SYMMETRIC
