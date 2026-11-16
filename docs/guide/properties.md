# Properties and units

A USIF property is a named value with a dtype and a unit. Properties live in two maps on every `Structure`:

| Map | Scope | Value shape |
|---|---|---|
| `structure.arrays` | per atom | array whose leading dimension is the atom count N, or a JSON list of N entries |
| `structure.properties` | per structure | scalar, array or JSON value |

Both are `usif.model.PropertyMap` objects. They validate and normalise every value on assignment, and they never convert values between units. The code is in `usif/model/properties.py` and `usif/units.py`.

## Setting and reading values

```python
import numpy as np
from usif import Cell, Structure

s = Structure(["Fe", "Fe"], [[0, 0, 0], [1.4, 1.4, 1.4]], Cell.cubic(2.8))

s.properties["energy"] = -16.4                   # unit from the schema: eV
s.properties.set("pressure", 1.2, unit="kbar")   # explicit unit overrides the schema unit
s.properties["stress"] = np.eye(3) * 0.1         # 3x3 tensor stored in Voigt order (6,)
s.properties["calculation"] = {"code": "VASP", "encut": 520}  # any JSON value
s.properties["kpoints"] = [8, 8, 8]              # undeclared numeric: int64 array, no unit
s.arrays["magmom"] = [2.2, -2.2]                 # unit: μB
s.arrays.set("bader_charge", [0.4, -0.4], unit="e")
s.arrays["site_label"] = ["a", "b"]              # per-atom JSON list

print(s.properties.units())   # {'energy': 'eV', 'pressure': 'kbar', 'stress': 'GPa', 'calculation': '', 'kpoints': ''}
print(s.properties.dtype("energy"), s.properties.dtype("calculation"))   # <f8 json
print(s.properties["energy"])                    # -16.4 (a Python float)
```

`PropertyMap` is a `MutableMapping[str, Any]` with these extra methods:

| Method | Meaning |
|---|---|
| `set(name, value, unit=None)` | Store a value. `unit=None` uses the schema unit for known names and no unit (`""`) otherwise. |
| `set_unit(name, unit)` | Change the unit label of a stored value (the value is not touched). |
| `unit(name)`, `units()` | The unit of one value, or a `{name: unit}` dict. |
| `dtype(name)` | A NumPy dtype string such as `'<f8'`, or `"json"`. |
| `raw(name)` | The stored value: a read-only array for numeric values, JSON data otherwise. |
| `update_from(mapping)` | `set()` every item of a mapping (used by the `Structure` constructor). |
| `copy()`, `subset(index)` | A copy; `subset` reorders or selects atoms of a per-atom map. |
| `allclose(other, atol)` | Tolerant comparison of floating-point values (units must match). |

Reading with `map[name]` returns a Python scalar for 0-d numeric values, a read-only NumPy array for other numeric values, and a deep copy of JSON values. To change a numeric array, assign a new one; in-place writes raise `ValueError`.

## Normalisation rules

For a name with a `PropertySpec` in the structure's schema:

- an optional `coerce` function runs first (the built-in `stress` spec turns a 3x3 tensor into a Voigt 6-vector);
- the value is cast to the spec dtype with NumPy `same_kind` casting, so an int becomes a float64 `energy`, but a float is rejected for the int64 `spin_multiplicity`;
- the per-entry shape must equal the spec shape (the atom axis is excluded for per-atom specs); a spec shape of `None` accepts any shape;
- the default unit is the spec unit.

For a name without a spec:

- numeric input (bool, integer or float, including lists of numbers) is stored as an array with an inferred dtype; float16 and other dtypes outside the whitelist are widened to float64 or int64;
- strings, mappings and mixed lists are stored as JSON;
- the default unit is `""`; give one with `set(name, value, unit=...)`.

In all cases:

- numeric values must be finite (`nan`/`inf` raise `ValidationError`);
- per-atom values need leading dimension N (or N list entries for JSON);
- JSON values may contain only dicts with string keys, lists, strings, finite numbers, booleans and `None`; NumPy scalars, arrays and tuples are converted;
- names are non-empty strings of at most 255 UTF-8 bytes without control characters.

The numeric dtypes a value may have are bool, int8-int64, uint8-uint64, float32 and float64 (`usif.model.properties.NUMERIC_DTYPES`). Records and JSON documents store dtype and unit with each value, so a decoded structure compares equal to the original.

## Built-in specs (`DEFAULT_SCHEMA`)

Per atom (`structure.arrays`):

| Name | dtype | Entry shape | Unit | Description |
|---|---|---|---|---|
| `force` | float64 | `(3,)` | `eV/Å` | Force on the atom |
| `charge` | float64 | `()` | `e` | Atomic (partial) charge |
| `magmom` | float64 | `()` or `(3,)` | `μB` | Magnetic moment: collinear scalar or non-collinear 3-vector |
| `velocity` | float64 | `(3,)` | `Å/fs` | Atomic velocity |

Per structure (`structure.properties`):

| Name | dtype | Shape | Unit | Description |
|---|---|---|---|---|
| `energy` | float64 | `()` | `eV` | Total (potential) energy of the structure |
| `free_energy` | float64 | `()` | `eV` | Free energy (e.g. Mermin, with smearing) |
| `stress` | float64 | `(6,)` | `GPa` | Cauchy stress in Voigt order (xx, yy, zz, yz, xz, xy); a 3x3 tensor is converted. Positive is tensile, so pressure = -(xx + yy + zz)/3 (the ASE sign; VASP prints the opposite sign) |
| `pressure` | float64 | `()` | `GPa` | Pressure; positive is compressive |
| `dipole` | float64 | `(3,)` | `e·Å` | Electric dipole moment |
| `temperature` | float64 | `()` | `K` | Temperature |
| `charge` | float64 | `()` | `e` | Total charge |
| `spin_multiplicity` | int64 | `()` | (none) | Spin multiplicity 2S+1, at least 1 |

`usif.model.stress_to_voigt()` and `usif.model.voigt_to_tensor()` convert between the two stress layouts.

## Custom schemas

A `Schema` holds the specs of the two scopes. To fix the dtype, shape and unit of your own names, copy the default schema, register specs, and pass the schema to `Structure`, `usif.read`, `usif.decode` or `Dataset`:

```python
import numpy as np
from usif import DEFAULT_SCHEMA, Cell, PropertySpec, Structure

schema = DEFAULT_SCHEMA.copy()
schema.register(PropertySpec("band_gap", "float64", (), "eV", "Band gap"), per_atom=False)
schema.register(PropertySpec("born_charge", "float64", (3, 3), "e", "Born effective charge"),
                per_atom=True)

s = Structure(
    ["Na", "Cl"], [[0, 0, 0], [2.82, 2.82, 2.82]], Cell.cubic(5.64),
    arrays={"born_charge": np.stack([np.eye(3) * 1.1, np.eye(3) * -1.1])},
    properties={"band_gap": 5},          # an int is cast to float64
    schema=schema,
)
print(s.arrays.units(), s.properties.units(), s.properties.dtype("band_gap"))

try:
    s.arrays["born_charge"] = np.zeros((2, 3))   # wrong entry shape
except ValueError as exc:                        # usif.ValidationError
    print(exc)
```

`PropertySpec(name, dtype, shape=(), unit="", description="", coerce=None)` takes a numeric dtype or `"json"` (`usif.model.JSON`). Registering a name that already exists replaces it. Mutating `DEFAULT_SCHEMA` itself affects every structure that uses it, so prefer a copy.

Files written with a custom schema decode without it, because records and JSON documents carry dtype and unit with each value. Passing the schema when decoding validates the stored values against your specs again.

## Units

`usif.units.normalize_unit()` canonicalises unit spellings. It never converts values. The rules:

- `None` and blank strings become `""`;
- the Ångström sign (U+212B) becomes `Å`; the words `Ang`, `angstrom` and `angstroms` (any case) become `Å`;
- Unicode superscripts and `**` become caret exponents: `Å²` and `Å ** 2` -> `Å^2`;
- whitespace around `/` and `^` is removed, other whitespace collapses to one space: `eV / Angstrom` -> `eV/Å`;
- Unicode is NFC-normalised, so a decomposed `Å` reads `Å`; the MICRO SIGN `µ` becomes Greek `μ`;
- `micro` becomes `μ`; the words `mu_B`, `muB` and `uB` become `μB`; `bohr` becomes `Bohr`.

Normalisation is idempotent, and records only store normalised spellings.

```python
from usif.units import normalize_unit

for unit in ["Å²", "Ang^2", "angstrom^2", "eV / Angstrom", "muB", None]:
    print(repr(unit), "->", repr(normalize_unit(unit)))
```

### Conversion when values leave USIF

Stored values are never converted. Conversion happens only where a value must leave USIF in a fixed unit system: `usif.units.convert(value, from_unit, to_unit)` knows the common units of energy (eV, meV, Ha, Hartree, Ry, kJ/mol, kcal/mol), force (eV/Å, meV/Å, Ha/Bohr, Ry/Bohr, kcal/mol/Å), pressure and stress (GPa, MPa, Pa, kbar, bar, atm, eV/Å^3), length (Å, nm, pm, Bohr), velocity (Å/fs, Å/ps, m/s, km/s), charge (e) and magnetic moment (μB), with CODATA 2018 constants (1 eV/Å^3 = 160.2176634 GPa, `usif.units.EV_PER_ANG3_IN_GPA`). Units of different quantities, or unknown units, raise `ValidationError`.

```python
from usif.units import convert

print(convert(10.0, "kbar", "GPa"))      # 1.0
print(convert(1.0, "Ha/Bohr", "eV/Å"))   # 51.42206747...
```

The backends use it for the built-in quantities:

| Library | Exported in | Imported as |
|---|---|---|
| ASE | eV, eV/Å, eV/Å³ (stress, via `ase.units.GPa`), Å/fs → ASE time units, e, μB, e·Å | the default-schema units (stress in GPa) |
| matsimpy | eV, eV/Å, Å/fs, e, μB; `metadata["stress"]` as a 3x3 tensor in eV/Å³ | the default-schema units |
| pymatgen | the default-schema units (pymatgen stores bare numbers) | the default-schema units |

A built-in quantity whose stored unit cannot be converted makes the export fail with `ValidationError` instead of handing the library a wrong number. Custom properties are passed through unchanged. See [Other libraries](libraries.md) for the full mapping.

## Properties in datasets

A `Dataset` indexes every numeric 0-d structure property (for example `energy`, `band_gap`) so it can be filtered with `Q.prop(name)` and `Q.has_prop(name)`. Arrays, per-atom values and JSON values are stored in the record but are not queryable; put values you want to filter on into scalar structure properties or into entry attributes (`Q.attr`). See [Datasets](datasets.md#queries).
