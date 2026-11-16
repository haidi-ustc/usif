# Structures

`usif.Structure` is a molecule or periodic structure stored as arrays.

```text
Structure(numbers, positions, cell=None, *, pbc=None, arrays=None, properties=None, schema=DEFAULT_SCHEMA)
Structure.from_fractional(numbers, fractional, cell, **kwargs)
```

| Argument | Meaning |
|---|---|
| `numbers` | Atomic numbers (1-118) or element symbols, length N. Stored as read-only `uint8`. |
| `positions` | Cartesian coordinates in Å, shape (N, 3). Stored as read-only `float64`. |
| `cell` | A `Cell`, a 3x3 matrix whose rows are lattice vectors (a length-3 vector means a diagonal matrix), or `None` for a molecule. |
| `pbc` | Periodic flags when `cell` is a matrix: one bool or three. Defaults to all `True`. A true `pbc` flag without a cell is an error. |
| `arrays` | Per-atom properties `{name: value with leading dimension N}`. |
| `properties` | Structure properties `{name: scalar, array or JSON value}`. |
| `schema` | The `Schema` used to validate properties and supply default units. |

Construction validates everything: at least one atom, finite positions of the right shape, a non-degenerate finite cell, and property values (see [Properties and units](properties.md)). Invalid input raises `usif.ValidationError` (a `ValueError`).

## Cell

`Cell(matrix, pbc=True)` is immutable. It offers `matrix`, `pbc`, `is_periodic`, `volume`, `lengths`, `angles` (degrees), `inverse`, `to_fractional()`, `to_cartesian()`, `allclose()` and `Cell.cubic(a)`.

## Derived values

These are computed from the geometry and never stored:

```python
from usif import Cell, Structure

s = Structure.from_fractional(["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(5.64))
s.natoms, len(s)            # 2, 2
s.symbols                   # ['Na', 'Cl']
s.formula                   # 'NaCl' (unreduced: a supercell gives 'Na4Cl4')
s.reduced_formula           # 'NaCl'
s.chemical_system           # 'Cl-Na'
s.element_counts            # {'Na': 1, 'Cl': 1}
s.is_periodic, s.pbc        # True, (True, True, True)
s.volume                    # 179.406144 (None for a molecule)
s.frac_positions            # needs a cell
```

A structure is periodic when it has a cell with at least one periodic axis. There is no separate molecule or crystal type.

## Immutability and derivation

`numbers`, `positions` and the cell are read-only. Derive modified structures instead:

```python
moved = s.replace(positions=s.positions + 0.01)   # keeps arrays and properties
bigger = s.replace(cell=Cell.cubic(6.0))           # cell=None removes the cell
reordered = s.permute([1, 0])                      # reorders per-atom arrays too
clone = s.copy()
```

`replace()` keeps per-atom arrays only when the atom count is unchanged; pass `keep_properties=False` to drop all properties.

`arrays` and `properties` are mutable `PropertyMap` objects; numeric values inside them are read-only arrays, so assign a new value to change one.

## Equality

`==` is exact: numbers, positions, cell, and every property value, dtype and unit must match. `s.allclose(other, atol=1e-8)` compares positions, cell and floating-point properties within `atol`. Structures are not hashable; use the record hash (see [Records and JSON](records.md#identity-hashes)) as an identity.
