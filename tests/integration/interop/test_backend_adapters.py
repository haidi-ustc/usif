"""Behaviour of the matsimpy, pymatgen and ASE adapters and the array layer."""

from __future__ import annotations

import numpy as np
import pytest

from usif import USIF, CompressionType, StorageMode, StructureType
from usif.exceptions import ValidationError
from usif.integrations.materials_project.mapper import atoms_from_structure_dict
from usif.interop.common import build_structure, structure_to_arrays
from usif.services import export_structure, import_structure

ROCKSALT = (
    [11] * 4 + [17] * 4,
    [[0, 0, 0], [0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]]
    + [[0.5, 0.5, 0.5], [0.5, 0, 0], [0, 0.5, 0], [0, 0, 0.5]],
)


# -- backend-free array layer -------------------------------------------------


def test_records_with_more_than_255_sites_roundtrip():
    rng = np.random.default_rng(0)
    count = 300
    structure = build_structure(
        [1 + i % 20 for i in range(count)],
        rng.random((count, 3)),
        lattice=np.eye(3) * 20.0,
        cartesian=False,
        atomic={"force": rng.normal(size=(count, 3))},
    )
    codec = USIF(compression=CompressionType.NONE)
    decoded, _ = codec.decode(codec.encode(structure))
    assert len(decoded.atom_sites) == count
    assert codec.get_record_hash(decoded) == codec.get_record_hash(structure)


def test_symmetric_structures_expand_to_arrays():
    numbers, frac = ROCKSALT
    full = build_structure(numbers, frac, lattice=np.eye(3) * 5.64, cartesian=False)
    reduced = _analyze(full)
    assert reduced.storage_mode == StorageMode.SYMMETRIC
    data = structure_to_arrays(reduced)
    assert sorted(data.numbers) == sorted(numbers)
    assert np.allclose(data.lattice, full.lattice_matrix)


def _analyze(structure):
    from usif.symmetry import SymmetryPolicy, apply_symmetry_policy

    return apply_symmetry_policy(structure, SymmetryPolicy(mode="analyze"))


def test_partial_pbc_is_preserved():
    structure = build_structure([6], [[0, 0, 0]], lattice=np.eye(3) * 3.0, pbc=(True, True, False))
    assert structure_to_arrays(structure).pbc == (True, True, False)


# -- Materials Project documents (no pymatgen) --------------------------------


def _mp_doc(species):
    return {
        "lattice": {"matrix": [[4.0, 0, 0], [0, 4.0, 0], [0, 0, 4.0]]},
        "sites": [
            {"species": species, "abc": [0, 0, 0], "properties": {"magmom": 2.0}},
        ],
    }


def test_mp_structure_dict_is_parsed_without_pymatgen():
    data = atoms_from_structure_dict(
        _mp_doc([{"element": "Fe", "occu": 1.0, "oxidation_state": 3}])
    )
    assert data.numbers == [26]
    assert data.atomic["magmom"] == [2.0]
    assert data.site_custom[0]["oxidation_state"] == 3.0


def test_mp_structure_dict_rejects_disorder():
    with pytest.raises(ValidationError, match="disordered"):
        atoms_from_structure_dict(
            _mp_doc([{"element": "Fe", "occu": 0.5}, {"element": "Ni", "occu": 0.5}])
        )


# -- pymatgen -----------------------------------------------------------------


def test_pymatgen_oxidation_states_charge_and_spin_roundtrip():
    pytest.importorskip("pymatgen")
    from pymatgen.core import Lattice, Molecule, Species, Structure

    crystal = Structure(
        Lattice.cubic(4.2), [Species("Mg", 2), Species("O", -2)], [[0, 0, 0], [0.5, 0.5, 0.5]]
    )
    back = export_structure(import_structure(crystal), fmt="pymatgen")
    assert [s.oxi_state for s in back.species] == [2, -2]

    radical = Molecule(["O", "H"], [[0, 0, 0], [0, 0, 0.97]], charge=-1, spin_multiplicity=1)
    triplet = Molecule(["O", "O"], [[0, 0, 0], [0, 0, 1.21]], spin_multiplicity=3)
    for mol in (radical, triplet):
        out = export_structure(import_structure(mol), fmt="pymatgen")
        assert out.charge == mol.charge
        assert out.spin_multiplicity == mol.spin_multiplicity


def test_pymatgen_disordered_structure_is_rejected():
    pytest.importorskip("pymatgen")
    from pymatgen.core import Lattice, Structure

    alloy = Structure(Lattice.cubic(3.6), [{"Fe": 0.5, "Ni": 0.5}], [[0, 0, 0]])
    with pytest.raises(ValidationError, match="Disordered"):
        import_structure(alloy)


def test_pymatgen_site_magmoms_keep_antiferromagnetic_order():
    pytest.importorskip("pymatgen")
    from pymatgen.core import Lattice, Structure

    afm = Structure(
        Lattice.cubic(2.87),
        ["Fe", "Fe"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
        site_properties={"magmom": [2.2, -2.2]},
    )
    structure = import_structure(afm, symmetry_policy=None)
    assert structure.storage_mode == StorageMode.FULL_ATOMIC
    assert [site.properties.magmom for site in structure.atom_sites] == [2.2, -2.2]


# -- ASE ----------------------------------------------------------------------


def test_ase_stress_and_velocity_units_and_pbc():
    pytest.importorskip("ase")
    from ase import Atoms, units
    from ase.calculators.singlepoint import SinglePointCalculator

    atoms = Atoms("Cu", positions=[[0, 0, 0]], cell=np.eye(3) * 3.6, pbc=(True, True, False))
    atoms.set_velocities([[1.0 / units.fs, 0, 0]])  # 1 Å/fs in ASE units
    stress_ev = np.array([0.01, 0.02, 0.03, 0.0, 0.0, 0.0])
    atoms.calc = SinglePointCalculator(atoms, energy=-3.5, stress=stress_ev)

    structure = import_structure(atoms)
    assert structure.structure_type == StructureType.CRYSTAL
    assert structure.structure_properties.energy == pytest.approx(-3.5)
    stress = structure.structure_properties.get("stress")
    assert stress[0] == pytest.approx(0.01 * 160.21766208)
    assert structure.atom_sites[0].properties.get("velocity")[0] == pytest.approx(1.0)

    back = export_structure(structure, fmt="ase")
    assert tuple(back.pbc) == (True, True, False)
    assert back.get_stress()[0] == pytest.approx(0.01)
    assert back.get_velocities()[0, 0] == pytest.approx(1.0 / units.fs)


def test_ase_molecule_without_cell_is_a_molecule():
    pytest.importorskip("ase")
    from ase import Atoms

    structure = import_structure(Atoms("H2", positions=[[0, 0, 0], [0, 0, 0.74]]))
    assert structure.structure_type == StructureType.MOLECULE
    assert structure.formula == "H2"


# -- matsimpy -----------------------------------------------------------------


def test_matsimpy_crystal_roundtrip_keeps_properties():
    matsimpy = pytest.importorskip("matsimpy")

    crystal = matsimpy.Crystal(
        ["Fe", "Fe"],
        [[0, 0, 0], [1.435, 1.435, 1.435]],
        matsimpy.Lattice([[2.87, 0, 0], [0, 2.87, 0], [0, 0, 2.87]]),
        coords_are_cartesian=True,
        site_properties=[{"magmom": 2.2, "tag": 1}, {"magmom": -2.2, "tag": 2}],
        metadata={"energy": -16.5, "source": "test"},
    )
    structure = import_structure(crystal)
    assert structure.formula == "Fe"
    assert structure.structure_properties.energy == pytest.approx(-16.5)
    assert structure.structure_properties.custom["source"] == "test"
    assert [s.properties.magmom for s in structure.atom_sites] == [2.2, -2.2]

    back = export_structure(structure, fmt="matsimpy")
    assert [p["magmom"] for p in back.site_properties] == [2.2, -2.2]
    assert [p["tag"] for p in back.site_properties] == [1, 2]
    assert back.metadata["energy"] == pytest.approx(-16.5)
    assert np.allclose(back.positions, crystal.positions)


def test_matsimpy_and_pymatgen_give_identical_records():
    matsimpy = pytest.importorskip("matsimpy")
    pytest.importorskip("pymatgen")
    from pymatgen.core import Lattice, Structure

    numbers, frac = ROCKSALT
    cart = (np.array(frac, dtype=float) * 5.64).tolist()
    species = ["Na" if z == 11 else "Cl" for z in numbers]
    via_matsimpy = import_structure(
        matsimpy.Crystal(
            species, cart, matsimpy.Lattice(np.eye(3) * 5.64), coords_are_cartesian=True
        )
    )
    via_pymatgen = import_structure(Structure(Lattice.cubic(5.64), species, frac))
    codec = USIF()
    assert codec.get_record_hash(via_matsimpy) == codec.get_record_hash(via_pymatgen)


def test_matsimpy_molecule_roundtrip():
    matsimpy = pytest.importorskip("matsimpy")

    molecule = matsimpy.Molecule(["O", "H", "H"], [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]])
    structure = import_structure(molecule)
    assert structure.structure_type == StructureType.MOLECULE
    assert structure.formula == "H2O"
    back = export_structure(structure, fmt="matsimpy")
    assert np.allclose(back.positions, molecule.positions)
