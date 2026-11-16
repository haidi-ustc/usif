"""Backends (matsimpy, ASE, pymatgen, plugins) and usif.io dispatch."""

import subprocess
import sys

import numpy as np
import pytest

from usif import backends, io
from usif.codec import encode_with_info
from usif.errors import FormatError, ValidationError
from usif.model import Cell, Structure

ROCKSALT = [
    [0, 0, 0],
    [0, 0.5, 0.5],
    [0.5, 0, 0.5],
    [0.5, 0.5, 0],
    [0.5, 0.5, 0.5],
    [0.5, 0, 0],
    [0, 0.5, 0],
    [0, 0, 0.5],
]
BACKENDS = ["matsimpy", "ase", "pymatgen"]


def nacl() -> Structure:
    rng = np.random.default_rng(0)
    return Structure.from_fractional(
        [11] * 4 + [17] * 4,
        ROCKSALT,
        Cell.cubic(5.64),
        arrays={
            "force": rng.normal(size=(8, 3)),
            "charge": rng.normal(size=8),
            "tags": np.arange(8),
        },
        properties={"energy": -10.5, "stress": np.arange(6.0), "meta": {"code": "x"}},
    )


def water() -> Structure:
    return Structure(
        [8, 1, 1],
        [[0, 0, 0.1173], [0, 0.7572, -0.4692], [0, -0.7572, -0.4692]],
        properties={"charge": -1.0, "spin_multiplicity": 2},
    )


@pytest.fixture(params=BACKENDS)
def backend(request):
    pytest.importorskip(request.param)
    return request.param


class TestBackends:
    def test_registry_order(self):
        assert [b.name for b in backends.backends()][:3] == BACKENDS
        with pytest.raises(ValidationError):
            backends.get("nope")

    @pytest.mark.parametrize("make", [nacl, water], ids=["crystal", "molecule"])
    def test_round_trip_is_exact(self, backend, make):
        structure = make()
        obj = io.convert(structure, backend)
        assert backends.for_object(obj).name == backend
        back = io.convert(obj)
        assert back == structure

    def test_same_record_hash_through_every_backend(self):
        hashes = set()
        for name in BACKENDS:
            pytest.importorskip(name)
            hashes.add(encode_with_info(io.convert(io.convert(nacl(), name)))[1].record_hash)
        assert len(hashes) == 1

    def test_ase_calculator_units(self):
        pytest.importorskip("ase")
        atoms = io.convert(nacl(), "ase")
        # 1 GPa = 1/160.2 eV/Å^3 in ASE's stress
        assert np.isclose(atoms.get_stress(voigt=True)[1], 1.0 / 160.21766208)
        assert atoms.get_potential_energy() == -10.5

    def test_pymatgen_oxidation_states_and_disorder(self):
        core = pytest.importorskip("pymatgen.core")
        ordered = core.Structure(
            core.Lattice.cubic(4.0), ["Fe2+", "O2-"], [[0, 0, 0], [0.5, 0.5, 0.5]]
        )
        s = io.convert(ordered)
        assert s.arrays["oxidation_state"].tolist() == [2.0, -2.0]
        assert str(io.convert(s, "pymatgen")[0].specie) == "Fe2+"
        disordered = core.Structure(core.Lattice.cubic(4.0), [{"Fe": 0.5, "Ni": 0.5}], [[0, 0, 0]])
        with pytest.raises(ValidationError, match="disordered"):
            io.convert(disordered)

    def test_unknown_object(self):
        with pytest.raises(ValidationError, match="no backend"):
            io.convert(object())

    def test_plugin_backend(self):
        class Toy:
            name = "toy-plugin"

            def accepts(self, obj):
                return isinstance(obj, tuple) and obj[:1] == ("toy",)

            def to_structure(self, obj, *, schema=None):
                return Structure([1], [[0, 0, 0]])

            def from_structure(self, structure):
                return ("toy", structure.natoms)

        backends.register(Toy, replace=True)
        assert io.convert(("toy",)) == Structure([1], [[0, 0, 0]])
        assert io.convert(water(), "toy-plugin") == ("toy", 3)
        with pytest.raises(ValidationError):
            backends.register(object())

    def test_core_does_not_import_structure_libraries(self):
        code = (
            "import sys, usif.io, usif.backends, usif.dataset; from usif.model import Structure;"
            "usif.backends.for_object(object());"
            "s = Structure([1], [[0, 0, 0]]);"
            "assert not {'ase', 'pymatgen', 'matsimpy'} & set(sys.modules), sorted(sys.modules)"
        )
        subprocess.run([sys.executable, "-c", code], check=True)


class TestFiles:
    def test_native_files(self, tmp_path):
        s = nacl()
        io.write(s, tmp_path / "a.usif", symmetry="auto", compression="lzma")
        io.write(s, tmp_path / "a.usif.json")
        assert io.read(tmp_path / "a.usif") == s
        assert io.read(str(tmp_path / "a.usif.json")) == s
        assert io.read(s) is s

    def test_format5_records_are_read_transparently(self):
        assert io.read("tests/fixtures/format5/nacl_225.usif").reduced_formula == "NaCl"

    def test_native_errors(self, tmp_path):
        (tmp_path / "bad.usif").write_bytes(b"garbage")
        with pytest.raises(FormatError):
            io.read(tmp_path / "bad.usif")
        with pytest.raises(FileNotFoundError):
            io.read(tmp_path / "missing.usif")
        with pytest.raises(ValidationError, match="Dataset"):
            (tmp_path / "x.usifc").write_bytes(b"x")
            io.read(tmp_path / "x.usifc")
        with pytest.raises(ValidationError):
            io.write("not a structure", tmp_path / "a.usif")
        with pytest.raises(ValidationError, match="apply only"):
            pytest.importorskip("ase")
            io.write(nacl(), tmp_path / "a.cif", symmetry="auto")

    @pytest.mark.parametrize("name", ["nacl.cif", "POSCAR", "nacl.extxyz"])
    def test_foreign_files(self, tmp_path, name):
        pytest.importorskip("ase")
        s = nacl()
        io.write(s, tmp_path / name)
        back = io.read(tmp_path / name)
        assert back.natoms == 8 and back.reduced_formula == "NaCl"

    def test_multi_frame(self, tmp_path):
        pytest.importorskip("ase")
        frames = [nacl(), nacl().replace(positions=nacl().positions + 0.01)]
        io.write_all(frames, tmp_path / "traj.extxyz")
        back = io.read_all(tmp_path / "traj.extxyz")
        assert len(back) == 2 and back[1].allclose(frames[1], atol=1e-8)
        assert back[0].properties["meta"] == {"code": "x"}
        with pytest.raises(FormatError, match="read_all"):
            io.read(tmp_path / "traj.extxyz")
        with pytest.raises(ValidationError):
            io.write_all(frames, tmp_path / "x.usif")

    def test_explicit_backend_and_failures(self, tmp_path):
        pytest.importorskip("ase")
        io.write(water(), tmp_path / "w.xyz", backend="ase")
        assert io.read(tmp_path / "w.xyz", backend="ase").natoms == 3
        (tmp_path / "junk.cif").write_text("not a cif")
        with pytest.raises(FormatError, match="cannot read"):
            io.read(tmp_path / "junk.cif")


def test_write_rejects_options_of_the_other_format(tmp_path):
    from usif import Structure, write
    from usif.errors import ValidationError

    structure = Structure([1], [[0.0, 0.0, 0.0]])
    with pytest.raises(ValidationError, match="indent"):
        write(structure, tmp_path / "h.usif", indent=2)
    with pytest.raises(ValidationError, match="compression"):
        write(structure, tmp_path / "h.json", compression="lzma")


def test_ase_export_converts_stored_units():
    pytest.importorskip("ase")
    from ase import units

    s = Structure([1, 1], [[0, 0, 0], [0.74, 0, 0]], Cell.cubic(5.0))
    s.properties.set("energy", -1000.0, unit="meV")
    s.properties.set("stress", [10.0, 20.0, 30.0, 0, 0, 0], unit="kbar")
    s.arrays.set("force", [[1, 0, 0], [-1, 0, 0]], unit="Ha/Bohr")
    atoms = io.convert(s, "ase")
    assert atoms.get_potential_energy() == pytest.approx(-1.0)
    assert atoms.get_forces()[0, 0] == pytest.approx(51.42206747632)
    assert atoms.get_stress(voigt=False)[2, 2] == pytest.approx(3.0 * units.GPa)
    back = io.convert(atoms)
    assert back.properties.unit("stress") == "GPa"
    assert back.properties["stress"][:3] == pytest.approx([1.0, 2.0, 3.0])
    s.properties.set("energy", 1.0, unit="furlong")
    with pytest.raises(ValidationError, match="energy"):
        io.convert(s, "ase")


def test_ase_free_energy_and_dipole():
    pytest.importorskip("ase")
    from ase import Atoms
    from ase.calculators.singlepoint import SinglePointCalculator

    atoms = Atoms("H2O", positions=[[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]])
    atoms.calc = SinglePointCalculator(atoms, energy=-14.2, free_energy=-14.25, dipole=[0, 0.4, 0])
    s = io.convert(atoms)
    assert s.properties["free_energy"] == -14.25 and s.properties.unit("dipole") == "e·Å"
    again = io.convert(s, "ase")
    assert again.calc.results["free_energy"] == -14.25
    assert again.get_dipole_moment().tolist() == [0, 0.4, 0]


def test_matsimpy_stress_uses_ev_per_cubic_angstrom():
    pytest.importorskip("matsimpy")
    s = Structure([14], [[0, 0, 0]], Cell.cubic(3.0))
    s.properties["stress"] = [160.2176634, 0, 0, 0, 0, 0]  # GPa
    crystal = io.convert(s, "matsimpy")
    assert np.asarray(crystal.metadata["stress"])[0, 0] == pytest.approx(1.0)
    assert io.convert(crystal).properties["stress"][0] == pytest.approx(160.2176634)


def test_pymatgen_export_uses_standard_units():
    pytest.importorskip("pymatgen")
    s = Structure([14, 14], [[0, 0, 0], [1.3, 1.3, 1.3]], Cell.cubic(5.43))
    s.arrays.set("force", [[1.0, 0, 0], [-1.0, 0, 0]], unit="meV/Å")
    s.properties.set("energy", -2.0, unit="Ry")
    pmg = io.convert(s, "pymatgen")
    assert pmg.site_properties["forces"][0][0] == pytest.approx(1e-3)
    assert pmg.properties["energy"] == pytest.approx(-2.0 * 13.605693122994)
