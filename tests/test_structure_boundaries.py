"""Tests for USIFStructure facade delegation boundaries."""

import numpy as np

from usif import StorageMode, StructureProperties, StructureType, USIFStructure, WyckoffSite
from usif.structures.io import load_structure, save_structure
from usif.structures.source import convert_to, from_pymatgen


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


def test_structure_save_load_delegate_to_io_helper(tmp_path):
    structure = make_structure()
    path = tmp_path / "structure.usif"

    save_structure(structure, path)
    loaded = load_structure(USIFStructure, path)

    assert loaded == structure


def test_structure_to_delegate_matches_direct_source_helper():
    structure = make_structure()

    assert convert_to(structure, fmt="pymatgen").composition.reduced_formula == "Si"
    assert structure.to(fmt="pymatgen").composition.reduced_formula == "Si"


def test_from_pymatgen_helper_matches_facade():
    pmg = make_structure().to(fmt="pymatgen")

    from_helper = from_pymatgen(pmg, force_symmetric=True)
    from_facade = USIFStructure.from_pymatgen(pmg, force_symmetric=True)

    assert from_helper.formula == from_facade.formula
    assert from_helper.storage_mode == from_facade.storage_mode
