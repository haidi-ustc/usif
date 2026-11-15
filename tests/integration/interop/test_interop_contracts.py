"""Contract tests for typed interop boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from usif.exceptions import ValidationError
from usif.interop.common import (
    is_ase_atoms,
    is_matsimpy_object,
    is_pymatgen_molecule,
    is_pymatgen_object,
    is_pymatgen_structure,
    stress_to_voigt,
    voigt_to_tensor,
)


def test_pymatgen_type_guards_identify_supported_objects():
    pytest.importorskip("pymatgen")
    from pymatgen.core import Lattice, Molecule, Structure

    structure = Structure(Lattice.cubic(3.0), ["Si"], [[0, 0, 0]])
    molecule = Molecule(["H", "H"], [[0, 0, 0], [0, 0, 0.74]])

    assert is_pymatgen_structure(structure)
    assert is_pymatgen_object(structure)
    assert is_pymatgen_molecule(molecule)
    assert is_pymatgen_object(molecule)

    assert not is_pymatgen_structure(molecule)
    assert not is_pymatgen_molecule(structure)
    assert not is_pymatgen_object(object())
    assert not is_matsimpy_object(structure)


def test_ase_type_guard_uses_concrete_optional_dependency():
    pytest.importorskip("ase")
    from ase import Atoms

    atoms = Atoms("H2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]])
    assert is_ase_atoms(atoms)
    assert not is_ase_atoms(object())
    assert not is_pymatgen_object(atoms)


def test_type_guards_do_not_match_lookalike_names():
    class Structure:  # same name as pymatgen's, wrong module
        pass

    assert not is_pymatgen_structure(Structure())
    assert not is_pymatgen_object(Structure())


def test_pymatgen_importer_unsupported_object_error_is_explicit():
    from usif.interop.pymatgen import PymatgenImporter

    with pytest.raises(TypeError, match="Expected pymatgen Structure or Molecule"):
        PymatgenImporter.from_pymatgen(object())


def test_per_site_property_lengths_are_validated():
    pytest.importorskip("pymatgen")
    from pymatgen.core import Lattice, Structure

    from usif.interop.pymatgen import PymatgenImporter

    structure = Structure(Lattice.cubic(3.0), ["Si", "Si"], [[0, 0, 0], [0.5, 0.5, 0.5]])

    with pytest.raises(ValidationError, match="1 entries for 2 atoms"):
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
    np.testing.assert_array_equal(voigt_to_tensor(stress_to_voigt(tensor)), tensor)
    with pytest.raises(ValueError, match="stress must be"):
        stress_to_voigt([1, 2, 3])


def test_ase_adapter_does_not_import_pymatgen():
    source = Path("usif/interop/ase/adapter.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(name.split(".")[0] == "pymatgen" for name in imported)
    assert not any(name.startswith("usif.interop.pymatgen") for name in imported)
