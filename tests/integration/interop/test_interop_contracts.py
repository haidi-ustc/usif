"""Contract tests for typed interop boundaries."""

from __future__ import annotations

import numpy as np
import pytest
from pymatgen.core import Lattice, Molecule, Structure

from usif.interop.common import (
    PymatgenMoleculeLike,
    PymatgenStructureLike,
    is_ase_atoms,
    is_pymatgen_molecule,
    is_pymatgen_object,
    is_pymatgen_structure,
)
from usif.interop.pymatgen import PymatgenImporter
from usif.interop.pymatgen.property_extractor import stress_to_voigt


def test_pymatgen_type_guards_identify_supported_objects():
    structure = Structure(Lattice.cubic(3.0), ["Si"], [[0, 0, 0]])
    molecule = Molecule(["H", "H"], [[0, 0, 0], [0, 0, 0.74]])

    assert is_pymatgen_structure(structure)
    assert is_pymatgen_object(structure)
    assert isinstance(structure, PymatgenStructureLike)

    assert is_pymatgen_molecule(molecule)
    assert is_pymatgen_object(molecule)
    assert isinstance(molecule, PymatgenMoleculeLike)

    assert not is_pymatgen_structure(molecule)
    assert not is_pymatgen_molecule(structure)
    assert not is_pymatgen_object(object())


def test_ase_type_guard_uses_concrete_optional_dependency():
    pytest.importorskip("ase")
    from ase import Atoms

    atoms = Atoms("H2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]])
    assert is_ase_atoms(atoms)
    assert not is_ase_atoms(object())


def test_pymatgen_importer_unsupported_object_error_is_explicit():
    with pytest.raises(TypeError, match="Expected pymatgen Structure or Molecule"):
        PymatgenImporter.from_pymatgen(object())


def test_per_site_property_lengths_are_validated():
    structure = Structure(Lattice.cubic(3.0), ["Si", "Si"], [[0, 0, 0], [0.5, 0.5, 0.5]])

    with pytest.raises(ValueError, match="forces length must match"):
        PymatgenImporter.from_pymatgen(structure, forces=np.array([[0.0, 0.0, 0.0]]))


def test_stress_tensor_uses_usif_voigt_order():
    tensor = np.array(
        [
            [1.0, 6.0, 5.0],
            [6.0, 2.0, 4.0],
            [5.0, 4.0, 3.0],
        ]
    )

    assert stress_to_voigt(tensor) == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    assert stress_to_voigt([1, 2, 3, 4, 5, 6]) == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    with pytest.raises(ValueError, match="stress must be"):
        stress_to_voigt([1, 2, 3])


def test_ase_adapter_documents_pymatgen_dependency():
    from usif.interop.ase.importer import ASEImporter

    doc = ASEImporter.from_ase.__doc__ or ""
    assert "pymatgen" in doc
    assert "AseAtomsAdaptor" in doc
