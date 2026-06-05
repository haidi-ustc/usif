"""Regression tests for P4 architecture cleanup fixes."""

import numpy as np
import pytest


def test_query_numeric_tolerance_is_distinct_from_symmetry_tolerance():
    # Pure constant check: no heavy dependencies required.
    from usif.constants import QueryConstants, SymmetryConstants

    assert hasattr(QueryConstants, "DEFAULT_NUMERIC_TOLERANCE")
    # Decoupled concept, even if the current numeric value coincides.
    assert isinstance(QueryConstants.DEFAULT_NUMERIC_TOLERANCE, float)
    assert QueryConstants.DEFAULT_NUMERIC_TOLERANCE > 0
    assert (
        QueryConstants.DEFAULT_NUMERIC_TOLERANCE
        is not SymmetryConstants.COORDINATE_TOLERANCE
    )


def test_mixed_per_atom_properties_roundtrip_to_pymatgen():
    pytest.importorskip("pymatgen")

    from usif import (
        AtomicProperties,
        AtomSite,
        StorageMode,
        StructureConverter,
        StructureType,
        USIFStructure,
    )

    # First atom carries a force, second atom does not. Previously this produced
    # a forces list of length 1 for a 2-site structure and pymatgen raised.
    structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3) * 3.0,
        spacegroup=1,
        atom_sites=[
            AtomSite(1, (0.0, 0.0, 0.0), AtomicProperties(force=(0.1, 0.0, 0.0))),
            AtomSite(1, (0.5, 0.5, 0.5), AtomicProperties()),
        ],
        formula="H2",
    )

    pmg = StructureConverter.to_pymatgen(structure)

    forces = pmg.site_properties.get("forces")
    assert forces is not None
    assert len(forces) == len(pmg)  # index-aligned, no length mismatch
    assert tuple(forces[0]) == (0.1, 0.0, 0.0)
    assert tuple(forces[1]) == (0.0, 0.0, 0.0)  # neutral default for missing value


def test_reduce_crystal_does_not_mutate_input_structure():
    pytest.importorskip("pymatgen")

    from usif import (
        AtomicProperties,
        AtomSite,
        StorageMode,
        StructureType,
        USIFStructure,
    )
    from usif.structures.metadata import SYMMETRY_METADATA_KEY
    from usif.symmetry import SymmetryReducer

    structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3) * 3.0,
        spacegroup=1,
        atom_sites=[AtomSite(1, (0.0, 0.0, 0.0), AtomicProperties())],
        formula="H",
    )

    custom_keys_before = set(structure.structure_properties.custom.keys())
    reduced = SymmetryReducer.reduce_crystal(structure, tolerance=0.1)

    # The original must be untouched regardless of whether reduction succeeded.
    assert SYMMETRY_METADATA_KEY not in structure.structure_properties.custom
    assert set(structure.structure_properties.custom.keys()) == custom_keys_before
    # If reduction produced a new symmetric structure, metadata lives on it only.
    if reduced is not structure:
        assert reduced.structure_properties is not structure.structure_properties


def test_shared_wyckoff_extractor_is_importable():
    pytest.importorskip("pymatgen")

    from usif.symmetry import extract_wyckoff_sites

    assert callable(extract_wyckoff_sites)
