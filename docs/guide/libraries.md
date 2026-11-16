# Other libraries

USIF converts structures to and from three optional libraries. Each is independent; install only the ones you use.

| Backend | Install | Objects |
|---|---|---|
| `matsimpy` | from its source checkout (not on PyPI) | `Crystal`, `Molecule` |
| `ase` | `pip install "usif[ase]"` | `Atoms` |
| `pymatgen` | `pip install "usif[pymatgen]"` | `Structure`, `IStructure`, `Molecule`, `IMolecule` |

[`examples/03_library_conversion.py`](../../examples/03_library_conversion.py) round-trips a structure through every installed backend.

## Objects

```python
import numpy as np
import usif
from usif import Cell, Structure

si = Structure.from_fractional(
    ["Si", "Si"],
    [[0, 0, 0], [0.25, 0.25, 0.25]],
    Cell([[0, 2.715, 2.715], [2.715, 0, 2.715], [2.715, 2.715, 0]]),
    arrays={"force": np.zeros((2, 3))},
    properties={"energy": -10.84, "stress": np.zeros(6)},
)

atoms = usif.convert(si, "ase")          # Structure -> ase.Atoms
pmg = usif.convert(si, "pymatgen")       # Structure -> pymatgen Structure
assert usif.convert(atoms) == si         # library object -> Structure
assert usif.read(pmg) == si              # usif.read accepts objects too
pmg_from_ase = usif.convert(atoms, "pymatgen")   # via a Structure
```

`usif.convert(obj)` finds the backend whose `accepts()` recognises the object. Backends recognise objects by class name, so `import usif` never imports a structure library; the library is imported when a conversion runs. A missing library raises `usif.MissingDependencyError` (an `ImportError`).

## Files

Any suffix other than `.usif`, `.json`, `.usif.json` and `.usifc` is handed to a backend. Without `backend=`, the installed backends are tried in the order matsimpy, ASE, pymatgen (then plugins) until one succeeds.

```python
usif.write(si, "si.extxyz")                          # ASE keeps forces, energy and stress
print(usif.read("si.extxyz").arrays.units())
usif.write(si, "POSCAR", backend="ase", format="vasp")
print(usif.read("POSCAR", backend="ase", format="vasp"))

usif.write_all([si, si.replace(positions=si.positions + 0.01)], "traj.extxyz")
frames = usif.read_all("traj.extxyz")                # usif.read() raises on multi-frame files
print(len(frames))
```

## What is mapped

| | matsimpy | ASE | pymatgen |
|---|---|---|---|
| Cell, pbc | `lattice.matrix` | `cell`, `pbc` (a zero cell means no cell) | `lattice` (with its `pbc`); `Molecule` has no cell |
| `force`, `charge`, `magmom`, `velocity` | per-site keys `force(s)`, `charge`, `magmom`, `velocit(y\|ies)` | calculator results; `initial_charges`/`initial_magmoms` without a calculator; velocities from momenta | site properties `forces`, `charge`, `magmom`, `velocities` |
| `energy`, `stress` and other built-in structure properties | `metadata` (stress as a 3x3 tensor in eV/Å³) | calculator results `energy`, `free_energy`, `stress` (eV/Å³ in ASE), `dipole` | `properties` dict |
| Other per-atom data | other per-site keys | other `arrays` (numeric only on export) | other site properties; `Species` oxidation states as `oxidation_state` |
| Other structure data | JSON-compatible `metadata` | JSON-compatible `info` | `properties`; `Molecule.charge` and `spin_multiplicity` |

Built-in quantities are converted to the library's units on export and back to the default-schema units on import (see [Properties and units](properties.md#conversion-when-values-leave-usif)); custom properties pass through unchanged. Values a backend cannot represent are skipped with a warning. pymatgen structures with partially occupied sites are rejected with `ValidationError`. Each backend module (`usif/backends/*.py`) documents its mapping in its docstring.

## Writing a backend

A backend converts one library's structure objects to and from `usif.Structure`. Once registered, `usif.convert` and `usif.read` accept that library's objects, and `usif.convert(structure, name)` produces them.

`usif.backends.Backend` requires:

| Member | Meaning |
|---|---|
| `name: str` | Registry name, also the library's import name. `usif.backends.available(name)` checks that it is importable. |
| `accepts(obj) -> bool` | True for the library's structure objects. Must not import the library; `usif.backends.is_instance_of(obj, "package", "ClassName")` checks by class name. |
| `to_structure(obj, *, schema=DEFAULT_SCHEMA) -> Structure` | Library object to `Structure`. |
| `from_structure(structure) -> Any` | `Structure` to library object. |

A `FileBackend` also implements `read(path, format=None, *, schema=DEFAULT_SCHEMA) -> list[Structure]` and `write(structures, path, format=None)`; then `usif.read`/`usif.write` use it for file formats too. If the library expects fixed units, convert built-in quantities with `usif.units.convert` using the stored unit (`structure.properties.unit(name)`).

```python
import usif
from usif import DEFAULT_SCHEMA, Structure
from usif.backends import register


class Molecule:                      # stands in for another library's class
    def __init__(self, symbols, xyz):
        self.symbols, self.xyz = symbols, xyz


class ToyBackend:
    name = "toykit"

    def accepts(self, obj):
        return isinstance(obj, Molecule)

    def to_structure(self, obj, *, schema=DEFAULT_SCHEMA):
        return Structure(obj.symbols, obj.xyz, schema=schema)

    def from_structure(self, structure):
        return Molecule(structure.symbols, structure.positions.tolist())


register(ToyBackend)                 # a class or an instance
water = usif.convert(Molecule(["O", "H", "H"], [[0, 0, 0], [0.96, 0, 0], [-0.24, 0.93, 0]]))
print(water, type(usif.convert(water, "toykit")).__name__)
```

`register(backend, *, replace=False)` appends to the lookup order (built-ins first: matsimpy, ASE, pymatgen); registering an existing name raises `ValidationError` unless `replace=True`.

Installed packages can register a backend without any import by the user. Point an entry point in the `usif.backends` group at the backend class or instance:

```toml
[project.entry-points."usif.backends"]
toykit = "toykit_usif:ToyBackend"
```

Entry points are loaded the first time the registry is used. A plugin that fails to load is skipped with a warning.
