"""Structure, Cell and PropertyMap behaviour."""

import numpy as np
import pytest

from usif.errors import ValidationError
from usif.model import DEFAULT_SCHEMA, Cell, PropertySpec, Schema, Structure

ROCKSALT_FRAC = [
    [0, 0, 0],
    [0, 0.5, 0.5],
    [0.5, 0, 0.5],
    [0.5, 0.5, 0],
    [0.5, 0.5, 0.5],
    [0.5, 0, 0],
    [0, 0.5, 0],
    [0, 0, 0.5],
]


def nacl() -> Structure:
    return Structure.from_fractional(["Na"] * 4 + ["Cl"] * 4, ROCKSALT_FRAC, Cell.cubic(5.64))


class TestCell:
    def test_derived_quantities(self):
        cell = Cell([[3, 0, 0], [0, 4, 0], [0, 0, 5]], pbc=(True, True, False))
        assert cell.volume == pytest.approx(60.0)
        assert np.allclose(cell.lengths, [3, 4, 5])
        assert np.allclose(cell.angles, [90, 90, 90])
        assert cell.pbc == (True, True, False)
        frac = cell.to_fractional([[1.5, 2.0, 2.5]])
        assert np.allclose(frac, [[0.5, 0.5, 0.5]])
        assert np.allclose(cell.to_cartesian(frac), [[1.5, 2.0, 2.5]])

    def test_diagonal_shorthand_and_equality(self):
        assert Cell([2, 3, 4]) == Cell(np.diag([2.0, 3.0, 4.0]))
        assert Cell([2, 3, 4]) != Cell([2, 3, 4], pbc=False)

    @pytest.mark.parametrize("matrix", [np.zeros((3, 3)), np.ones((2, 3)), [[np.inf, 0, 0]] * 3])
    def test_rejects_bad_matrices(self, matrix):
        with pytest.raises(ValidationError):
            Cell(matrix)

    def test_is_immutable(self):
        cell = Cell.cubic(3.0)
        with pytest.raises(ValueError):
            cell.matrix[0, 0] = 1.0


class TestStructure:
    def test_geometry_and_derived_data(self):
        s = nacl()
        assert s.natoms == len(s) == 8
        assert s.numbers.dtype == np.uint8
        assert s.is_periodic
        assert s.formula == "Na4Cl4"
        assert s.reduced_formula == "NaCl"
        assert s.chemical_system == "Cl-Na"
        assert s.element_counts == {"Na": 4, "Cl": 4}
        assert s.volume == pytest.approx(5.64**3)
        assert np.allclose(s.frac_positions, ROCKSALT_FRAC)

    def test_molecule(self):
        water = Structure([8, 1, 1], [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]])
        assert not water.is_periodic
        assert water.cell is None and water.volume is None
        assert water.pbc == (False, False, False)
        with pytest.raises(ValidationError):
            water.frac_positions

    def test_geometry_is_read_only_and_copied(self):
        positions = np.zeros((1, 3))
        s = Structure([1], positions)
        positions[0, 0] = 5.0
        assert s.positions[0, 0] == 0.0
        with pytest.raises(ValueError):
            s.positions[0, 0] = 1.0
        with pytest.raises(ValueError):
            s.numbers[0] = 2

    @pytest.mark.parametrize(
        "numbers, positions",
        [
            ([], np.zeros((0, 3))),
            ([0], [[0, 0, 0]]),
            ([119], [[0, 0, 0]]),
            ([1.5], [[0, 0, 0]]),
            ([1], [[0, 0]]),
            ([1], [[np.nan, 0, 0]]),
            (["Xx"], [[0, 0, 0]]),
        ],
    )
    def test_rejects_invalid_geometry(self, numbers, positions):
        with pytest.raises((ValidationError, KeyError, ValueError)):
            Structure(numbers, positions)

    def test_pbc_without_cell_is_rejected(self):
        with pytest.raises(ValidationError):
            Structure([1], [[0, 0, 0]], pbc=True)

    def test_partial_pbc(self):
        slab = Structure([6], [[0, 0, 0]], np.eye(3) * 3, pbc=(True, True, False))
        assert slab.pbc == (True, True, False) and slab.is_periodic

    def test_replace_and_permute(self):
        s = nacl()
        s.arrays["charge"] = np.arange(8, dtype=float)
        s.properties["energy"] = -1.0
        moved = s.replace(positions=s.positions + 0.1)
        assert moved.arrays == s.arrays and moved.properties == s.properties
        assert moved.cell == s.cell
        no_cell = s.replace(cell=None)
        assert no_cell.cell is None
        order = np.arange(8)[::-1]
        flipped = s.permute(order)
        assert flipped.symbols == s.symbols[::-1]
        assert np.array_equal(flipped.arrays["charge"], np.arange(8)[::-1])
        with pytest.raises(ValidationError):
            s.permute([0, 0, 1, 2, 3, 4, 5, 6])

    def test_equality_and_allclose(self):
        a, b = nacl(), nacl()
        assert a == b
        b.properties["energy"] = 1.0
        assert a != b
        shifted = a.replace(positions=a.positions + 1e-10)
        assert shifted != a and shifted.allclose(a, atol=1e-8)
        assert not shifted.allclose(a, atol=1e-12)

    def test_repr(self):
        assert repr(nacl()) == "Structure(Na4Cl4, natoms=8, periodic)"


class TestProperties:
    def test_schema_units_and_coercion(self):
        s = nacl()
        s.properties["stress"] = np.arange(9.0).reshape(3, 3)
        assert s.properties.unit("stress") == "GPa"
        assert s.properties["stress"].tolist() == [0.0, 4.0, 8.0, 5.0, 2.0, 1.0]
        s.arrays.set("force", np.zeros((8, 3)), unit="Hartree/Bohr")
        assert s.arrays.unit("force") == "Hartree/Bohr"
        s.properties["energy"] = -3
        assert isinstance(s.properties["energy"], float)

    def test_unit_spelling_is_normalised(self):
        s = nacl()
        s.properties.set("area", 4.0, unit="Ang^2")
        assert s.properties.unit("area") == "Å^2"
        from usif.units import normalize_unit

        assert normalize_unit("muB") == normalize_unit("uB") == "μB"
        assert normalize_unit("Angle") == "Angle"
        assert normalize_unit("club") == "club"

    def test_per_atom_shapes_are_checked(self):
        s = nacl()
        with pytest.raises(ValidationError):
            s.arrays["force"] = np.zeros((8, 2))
        with pytest.raises(ValidationError):
            s.arrays["charge"] = np.zeros(7)
        s.arrays["magmom"] = np.zeros(8)
        s.arrays["magmom"] = np.zeros((8, 3))  # non-collinear allowed

    def test_inferred_dtypes_and_json(self):
        s = nacl()
        s.arrays["tag"] = np.arange(8, dtype=np.int32)
        assert s.arrays.dtype("tag") == np.dtype("int32").str
        s.arrays["label"] = [f"site{i}" for i in range(8)]
        assert s.arrays.dtype("label") == "json"
        s.properties["meta"] = {"code": "VASP", "kpoints": np.array([4, 4, 4])}
        assert s.properties["meta"] == {"code": "VASP", "kpoints": [4, 4, 4]}
        s.properties["note"] = "relaxed"
        assert s.properties["note"] == "relaxed"
        s.properties["half"] = np.float16(0.5)
        assert s.properties.dtype("half") == np.dtype("float64").str

    @pytest.mark.parametrize(
        "value",
        [float("nan"), {"x": float("inf")}, {1: "a"}, object(), [object()]],
    )
    def test_rejects_unsafe_values(self, value):
        s = nacl()
        with pytest.raises(ValidationError):
            s.properties["bad"] = value

    def test_json_values_cannot_be_mutated_through_reads(self):
        s = nacl()
        s.properties["meta"] = {"a": [1]}
        s.properties["meta"]["a"].append(2)
        assert s.properties["meta"] == {"a": [1]}

    def test_spec_dtype_is_enforced(self):
        s = nacl()
        with pytest.raises(ValidationError):
            s.properties["spin_multiplicity"] = 1.5
        with pytest.raises(ValidationError):
            s.properties["energy"] = "low"

    def test_custom_schema(self):
        schema = Schema.default()
        schema.register(PropertySpec("bandgap", "float64", (), "eV"), per_atom=False)
        s = Structure([1], [[0, 0, 0]], schema=schema, properties={"bandgap": 1})
        assert s.properties.unit("bandgap") == "eV"
        assert DEFAULT_SCHEMA.structure("bandgap") is None

    @pytest.mark.parametrize("name", ["", "a\nb", "x" * 300])
    def test_rejects_bad_names(self, name):
        with pytest.raises(ValidationError):
            nacl().properties[name] = 1.0


class TestUnitsAndPhysics:
    @pytest.mark.parametrize(
        "spelling, canonical",
        [
            ("µB", "μB"),  # MICRO SIGN
            ("muB", "μB"),
            ("Å^2", "Å^2"),  # decomposed ring
            ("Å", "Å"),  # ANGSTROM SIGN
            ("eV / Ang", "eV/Å"),
            ("eV/Å³", "eV/Å^3"),
            ("Ha/bohr", "Ha/Bohr"),
            ("Angle", "Angle"),
            ("club", "club"),
        ],
    )
    def test_normalisation_is_canonical_and_idempotent(self, spelling, canonical):
        from usif.units import normalize_unit

        assert normalize_unit(spelling) == canonical
        assert normalize_unit(canonical) == canonical

    def test_conversion_constants(self):
        from usif.units import convert

        assert convert(1.0, "eV/Å^3", "GPa") == pytest.approx(160.2176634, rel=1e-12)
        assert convert(10.0, "kbar", "GPa") == pytest.approx(1.0)
        assert convert(1.0, "Ha", "eV") == pytest.approx(27.211386245988)
        assert convert(1.0, "Ha/Bohr", "eV/Å") == pytest.approx(51.42206747632, rel=1e-10)
        assert convert(1.0, "kcal/mol", "kJ/mol") == pytest.approx(4.184)
        assert convert(1.0, "Bohr", "Å") == pytest.approx(0.529177210903)
        assert convert(1.0, "km/s", "Å/fs") == pytest.approx(0.01)
        array = convert(np.array([1.0, 2.0]), "meV", "eV")
        assert array.tolist() == pytest.approx([1e-3, 2e-3])
        assert convert(5, "eV", "eV") == 5

    @pytest.mark.parametrize("pair", [("eV", "GPa"), ("furlong", "Å"), ("", "eV")])
    def test_conversion_errors(self, pair):
        from usif.units import convert

        with pytest.raises(ValidationError):
            convert(1.0, *pair)

    def test_schema_physics(self):
        s = nacl()
        stress = DEFAULT_SCHEMA.structure("stress")
        assert stress.unit == "GPa" and "tensile" in stress.description
        assert DEFAULT_SCHEMA.structure("dipole").shape == (3,)
        assert DEFAULT_SCHEMA.structure("free_energy").unit == "eV"
        with pytest.raises(ValidationError, match="magmom"):
            s.arrays["magmom"] = np.zeros((8, 2))
        with pytest.raises(ValidationError, match=">= 1"):
            s.properties["spin_multiplicity"] = 0
        with pytest.raises(ValidationError, match="out of range"):
            s.properties["spin_multiplicity"] = 2**64 - 1
