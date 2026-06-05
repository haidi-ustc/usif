# USIF Property System

This document describes the current property model implemented by `usif.properties`, `usif.format.binary.property_codec`, and `usif.properties.serializer`.

## 1. Property layers

USIF has two property layers:

| Layer | Class | Scope | Examples |
|---|---|---|---|
| structure-level | `StructureProperties` | one value for the whole structure | energy, stress, volume, pressure, temperature, custom metadata |
| atom-level | `AtomicProperties` | values attached to one `AtomSite` | force, charge, magmom, velocity, custom metadata |

Per-atom properties are stored only in `StorageMode.FULL_ATOMIC`. Symmetric imports reject per-atom property loss unless the caller explicitly chooses `drop_atomic_properties=True` or `fallback_full_atomic=True` through importer flags or `SymmetryPolicy`.

## 2. Built-in properties

The built-in registry is created by `PropertyRegistry.with_builtins()` and exposed as `DEFAULT_REGISTRY`.

| Name | Scope | Python type | Dimensions | Units |
|---|---|---|---|---|
| `force` | atom | `tuple` | `(3,)` | eV/Å |
| `charge` | atom | `float` | scalar | e |
| `magmom` | atom | `float` | scalar | μB |
| `velocity` | atom | `tuple` | `(3,)` | Å/fs |
| `energy` | structure | `float` | scalar | eV |
| `stress` | structure | `tuple` | `(6,)` | GPa |
| `volume` | structure | `float` | scalar | Å^3 |
| `pressure` | structure | `float` | scalar | GPa |
| `temperature` | structure | `float` | scalar | K |

Custom properties are stored in the `custom` dictionary on `StructureProperties` or `AtomicProperties`.

## 3. Registry model

The registry is instance-based:

```python
from usif import DEFAULT_REGISTRY, PropertyDefinition, create_default_registry

registry = create_default_registry()
registry.register(PropertyDefinition("formation_energy", float, units="eV/atom"))
```

`DEFAULT_REGISTRY` contains the process-wide built-ins. `create_default_registry()` returns an isolated copy that can be passed into `USIF(property_registry=registry)` or other codec/service paths that accept a registry. This avoids global mutable state in tests and applications.

Reserved property names include `type`, `name`, `units`, `description`, `id`, and `class`.

## 4. `PropertyDefinition`

A `PropertyDefinition` declares:

- `name`;
- `data_type` (`int`, `float`, `str`, `tuple`, `list`, or `bool`);
- `is_per_atom`;
- `dimensions`;
- `description`;
- `units`;
- optional requirement/default/range/allowed-value constraints.

Validation checks type compatibility, dimensional shape, numeric ranges, allowed values, and per-atom shape when atom count is supplied.

## 5. Structure properties

`StructureProperties` has explicit fields:

```python
StructureProperties(
    energy=-10.5,
    stress=(0, 0, 0, 0, 0, 0),
    volume=179.4,
    pressure=0.0,
    temperature=300.0,
    custom={"calculator": "VASP"},
)
```

`get_all_properties()` returns all non-`None` built-ins plus `custom` entries merged into one dictionary. `copy()` returns a deep copy.

## 6. Atomic properties

`AtomicProperties` has explicit fields:

```python
AtomicProperties(
    force=(0.0, 0.0, 0.0),
    charge=0.1,
    magmom=1.0,
    velocity=(0.0, 0.0, 0.0),
    custom={"site_label": "Na1"},
)
```

Vector fields must have exactly three numeric elements. `get_all_properties()` returns all set values plus custom entries.

## 7. Binary property section

Binary property sections are encoded by `PropertyCodec`:

```text
uint8 known_property_count
for each known property:
  uint8 name_length
  bytes name_utf8
  uint32 value_length
  bytes serialized_value
uint8 custom_property_count
for each custom property:
  uint8 name_length
  bytes name_utf8
  uint32 value_length
  bytes custom_value_utf8
```

Known properties are serialized by the public `PropertySerializer` facade according to their definitions. The public `PropertySerializer` delegates to focused modules under `usif.properties.serializers`: `scalar`, `vector`, `tensor`, `json_value`, `numpy_value`, `validation`, `size`, and `dispatch`. Custom values are encoded as JSON text with the prefix `__USIF_JSON__:` when JSON-compatible.

## 8. Value serialization

`PropertySerializer` uses these encodings:

| Definition | Encoding |
|---|---|
| `float` scalar | little-endian `float64` |
| `int` scalar | little-endian `int64` |
| `bool` scalar | little-endian boolean byte |
| `str` scalar | UTF-8 with short/long length encoding |
| dimensioned tuple/list | repeated numeric values |
| per-atom property | count byte plus encoded element(s) |

Per-atom count encoding:

| Count marker | Meaning |
|---:|---|
| `0` | one value, repeated for all atoms when applicable |
| `1..254` | exact count follows inline |
| `255` | uint32 count follows |

## 9. Custom values and JSON types

The binary `.usif` codec stores custom property values as UTF-8. `PropertyCodec.encode_custom_value()` JSON-serializes Python/scientific values and prefixes them with `__USIF_JSON__:`. `decode_custom_value()` restores JSON-compatible values such as dicts, lists, strings, numbers, booleans, and `null`.

Container structure/group attributes are also JSON-typed and preserve the same JSON-compatible value classes.

## 10. Symmetry and per-atom properties

Per-atom properties cannot be represented losslessly in symmetric storage because symmetric storage stores representative sites and multiplicities, not every atom. Importers therefore apply `SymmetryPolicy`:

- `mode="none"`: keep full-atomic storage;
- `mode="analyze"`: use symmetry only when no atom properties would be lost;
- `mode="reduce"`: prefer symmetry but require explicit drop or fallback behavior if atom properties exist;
- `mode="preserve"`: preserve source intent; pymatgen currently behaves like analyze.

This policy is shared by services, pymatgen importers, ASE importers, and `SymmetryReducer`.


## Official JSON structure documents

The service-level JSON schema `usif.structure.json.v1` serializes `USIFStructure.as_dict()` through `usif.services.structure_to_json_dict()` and stores `StructureProperties` as an explicit dictionary containing `energy`, `stress`, `volume`, `pressure`, `temperature`, and `custom`. JSON custom values preserve standard JSON-compatible values including dicts, lists, strings, numbers, booleans, and `null`.

Use `save_structure_json()` / `load_structure_json()` directly, or `save_structure()` / `load_structure()` with `.json` or `.usif.json` paths.


## 11. Ergonomic property management API

USIF provides a uniform property-management API for both structure-level and atom-level properties. The API is shape-aware and supports scalar, vector, tensor, and custom values without requiring callers to manipulate the `custom` dictionaries directly.

Structure-level properties:

```python
props = StructureProperties()
props.set_scalar("energy", -10.5)
props.set_tensor("stress", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
props.set_vector("dipole", [0.0, 0.0, 1.2])
props.set_tensor("elastic_tensor", zeros_3x3x3x3)
props.set_custom("calculation", {"code": "VASP", "converged": True})
```

Atom-level properties:

```python
atom_props = AtomicProperties()
atom_props.set_scalar("charge", -0.25)
atom_props.set_vector("force", [0.1, 0.0, 0.0])
atom_props.set_tensor("quadrupole", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
atom_props.set_custom("label", "O1")
```

Pure-model helpers on `USIFStructure` make atom-aligned property updates concise for full-atomic structures:

```python
structure.set_structure_property("energy", -10.5)
structure.set_atomic_property("charge", [1.0, -1.0])
structure.set_atomic_property("force", [[0, 0, 0], [0.1, 0.0, 0.0]])
structure.set_atom_property(1, "site_label", "Cl1")
```

Built-in properties are stored in their canonical representation: scalar built-ins as finite floats, `force`/`velocity` as 3-element tuples, and `stress` as the 6-element Voigt tuple `(xx, yy, zz, yz, xz, xy)`. `StructureProperties.stress_matrix()` returns the equivalent symmetric 3x3 matrix.

Custom properties are normalized to JSON-compatible values. Numpy scalars and arrays are accepted at API boundaries and become Python scalars/lists, which means custom scalar/vector/tensor values round-trip through binary `.usif`, JSON `.json` / `.usif.json`, and container `.usifc` records.

## 12. Unit metadata and aliases

The ergonomic property API stores unit metadata. Setters accept an
optional `units=` argument and normalize common Unicode/ASCII aliases. Unit
metadata is declarative: setters store and round-trip the unit string but do not
automatically convert numerical values.

```python
props = StructureProperties()
props.set_scalar("energy", -10.5)                         # default units: eV
props.set_tensor("stress", [[1, 0, 0], [0, 1, 0], [0, 0, 1]], units="GPa")
props.set_vector("dipole", [0.0, 0.0, 1.2], units="Debye")
props.set_tensor("quadrupole", [[1, 0, 0], [0, 1, 0], [0, 0, 1]], units="Ang^2")

atom = AtomicProperties()
atom.set_vector("force", [0.1, 0.0, 0.0], units="eV/Ang")
atom.set_tensor("quadrupole", [[1, 0, 0], [0, 1, 0], [0, 0, 1]], units="e Å²")
```

Canonical unit lookups return normalized spellings:

```python
props.get_units("energy")      # "eV"
props.get_units("quadrupole")  # "Å^2"
atom.get_units("force")        # "eV/Å"
```

The unit normalizer treats these forms as equivalent:

| User spelling | Canonical spelling |
|---|---|
| `Å²`, `Å^2`, `Ang^2`, `angstrom^2` | `Å^2` |
| `Å^3`, `Å^3`, `Ang^3`, `angstrom^3` | `Å^3` |
| `eV/Ang`, `eV/angstrom` | `eV/Å` |
| `cm⁻¹`, `cm^-1` | `cm^-1` |
| `g/cm³`, `g/cm^3` | `g/cm^3` |

Built-in properties keep default units when values are set:

| Property | Default units |
|---|---|
| `energy` | `eV` |
| `stress` | `GPa` |
| `volume` | `Å^3` |
| `pressure` | `GPa` |
| `temperature` | `K` |
| `force` | `eV/Å` |
| `charge` | `e` |
| `magmom` | `μB` |
| `velocity` | `Å/fs` |

Custom properties with unit metadata are stored as `PropertyValue` envelopes in
the JSON-compatible custom dictionary. Ergonomic getters still return the bare
payload value, while `get_custom_envelope()` exposes the full metadata envelope.
Unit metadata is preserved through `.usif`, `.json`, `.usif.json`, and `.usifc`
records.
