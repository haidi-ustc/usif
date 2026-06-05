# USIF — Universal Structure Interchange Format

USIF is a Python library for representing, converting, encoding, and grouping atomistic structures. It supports crystals and molecules, compact symmetry-aware storage, explicit full-atom storage with per-atom properties, binary `.usif` files, and multi-structure `.usifc` containers.

```python
from pymatgen.core import Lattice, Structure
from usif.services import import_structure, load_structure, save_structure

pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
structure = import_structure(pmg, energy=-10.5, calculator="VASP")
save_structure(structure, "nacl.usif")
loaded = load_structure("nacl.usif")
print(loaded.formula)
```

## What USIF provides

- One `USIFStructure` model for crystals and molecules.
- Binary `.usif` encoding with compression and integrity checks.
- `.usifc` containers for many structures, names, groups, attributes, and indexed queries.
- Conversion from and to pymatgen and ASE objects.
- A property model for energy, stress, temperature, pressure, volume, forces, charges, magnetic moments, and custom metadata.
- Materials Project helper utilities behind the optional `mp` extra.

## Installation

```bash
python -m pip install -e ".[dev,ase]"
python -m pip install -e ".[all]"  # include Materials Project tooling
```

Core runtime requirements are Python 3.10+, `numpy`, and `pymatgen`. ASE support is installed with the `ase` extra. Materials Project download support is installed with the `mp` extra and requires an API key.

## Quick start

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from pymatgen.core import Lattice, Structure
from usif.services import import_structure, load_structure, save_structure

with TemporaryDirectory() as tmp:
    pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    structure = import_structure(pmg, energy=-10.5, calculator="VASP")
    path = Path(tmp) / "nacl.usif"
    save_structure(structure, path)
    loaded = load_structure(path)
    print(loaded.formula)
```

Run it from the repository root:

```bash
python examples/quickstart.py
```

## Manual structure creation

```python
import numpy as np
from usif import StorageMode, StructureProperties, StructureType, USIFStructure, WyckoffSite

structure = USIFStructure(
    structure_type=StructureType.CRYSTAL,
    storage_mode=StorageMode.SYMMETRIC,
    lattice_matrix=np.eye(3) * 5.64,
    spacegroup=225,
    wyckoff_sites=[WyckoffSite(11, 4, (0, 0, 0)), WyckoffSite(17, 4, (0.5, 0.5, 0.5))],
    structure_properties=StructureProperties(energy=-10.5, custom={"calculator": "VASP"}),
    formula="NaCl",
)
print(structure.num_atoms())
```

## Binary encoding and integrity checks

```python
from pymatgen.core import Lattice, Structure
from usif import CompressionType, USIF
from usif.services import import_structure

pmg = Structure(Lattice.cubic(3.0), ["Li"], [[0, 0, 0]])
structure = import_structure(pmg, energy=-1.0)
codec = USIF(compression=CompressionType.GZIP)
data = codec.encode(structure)
decoded, geometry_hash = codec.decode(data)
print(len(data), geometry_hash.hex(), codec.get_record_hash(decoded))
```

Hash semantics are intentionally separate:

| Helper | Purpose |
|---|---|
| `get_geometry_hash()` | geometry-only identity for similarity/grouping |
| `get_record_hash()` | full logical record identity, including properties |
| binary payload digest | internal file integrity checks |

## Containers

`StructureContainer` stores many structures in a `.usifc` file. Records are deduplicated by `record_hash`, so two structures with the same geometry but different properties are preserved as distinct records.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from pymatgen.core import Lattice, Structure
from usif.services import import_structure
from usif.storage import StructureContainer

with TemporaryDirectory() as tmp:
    path = Path(tmp) / "materials.usifc"
    pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    low = import_structure(pmg, energy=-10.5)
    high = import_structure(pmg, energy=-10.0)
    with StructureContainer(path, mode="w") as container:
        print(container.add(low, name="nacl-low") != container.add(high, name="nacl-high"))
    with StructureContainer(path, mode="r") as container:
        print(container.query(formula="NaCl", energy_range=(-10.6, -10.1)))
```

Run the full container example:

```bash
python examples/container_query.py
```

Container internals are split across focused modules under `usif.storage`: `container.py` coordinates the public API, while attribute encoding, LRU caching, chunked I/O, group operations, index persistence, prefetch/batch reads, and recovery scanning live in separate modules.

## Conversion with pymatgen and ASE

USIF 5.6 keeps `USIFStructure` as a pure model; use services or explicit interop adapters at application boundaries. Use `PymatgenImporter` / `PymatgenExporter` and `ASEImporter` / `ASEExporter` for direct conversions.


```python
from pymatgen.core import Lattice, Structure
from usif.interop.pymatgen import PymatgenExporter
from usif.services import import_structure

pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
structure = import_structure(pmg, energy=-10.5)
round_tripped = PymatgenExporter.to_pymatgen(structure)
print(round_tripped.composition.reduced_formula)
```

ASE support requires the `ase` extra:

```python
from ase import Atoms
from usif.services import import_structure

atoms = Atoms("H2O", positions=[[0, 0, 0], [0.95, 0, 0], [0.95, 0.95, 0]])
water = import_structure(atoms, energy=-76.4)
print(water.formula)
```

Run the conversion example:

```bash
python examples/conversion_with_pymatgen.py
```

## Per-atom properties and hash semantics

Full-atom storage preserves per-atom forces, charges, magnetic moments, velocities, and custom atom metadata. Symmetric storage stores representative sites and multiplicities. To avoid silent data loss, `force_symmetric=True` rejects per-atom properties unless you explicitly choose `drop_atomic_properties=True` or `fallback_full_atomic=True`.

```python
import numpy as np
from usif import AtomicProperties, AtomSite, StorageMode, StructureProperties, StructureType, USIF, USIFStructure

atom = AtomSite(3, (0, 0, 0), AtomicProperties(force=(0, 0, 0)))
relaxed = USIFStructure(StructureType.CRYSTAL, StorageMode.FULL_ATOMIC, np.eye(3) * 3.0, atom_sites=[atom], structure_properties=StructureProperties(energy=-1.0), formula="Li")
excited = USIFStructure(StructureType.CRYSTAL, StorageMode.FULL_ATOMIC, np.eye(3) * 3.0, atom_sites=[atom], structure_properties=StructureProperties(energy=-0.5), formula="Li")
codec = USIF()
print(codec.get_geometry_hash(relaxed) == codec.get_geometry_hash(excited))
print(codec.get_record_hash(relaxed) == codec.get_record_hash(excited))
```

Run the property/hash example:

```bash
python examples/properties_and_hashes.py
```

## Materials Project utilities

```bash
python -m pip install -e ".[mp]"
export MP_API_KEY="your_key_here"
python examples/download_mp_data.py --total_entries 100 --entries_per_group 25
python examples/download_mp_data.py --help
```

Prefer the `MP_API_KEY` environment variable over command-line API keys because shell history and process listings may expose arguments.

## Repository examples

README-linked examples are executable from the repository root:

```bash
python examples/quickstart.py
python examples/container_query.py
python examples/conversion_with_pymatgen.py
python examples/properties_and_hashes.py
python examples/download_mp_data.py --help
```

## Development

```bash
python -m pip install -e ".[dev,ase]"
python -m pytest
python -m pytest --cov=usif --cov-report=term-missing --cov-fail-under=70
python -m black --check usif tests examples
python -m isort --check-only usif tests examples
python -m mypy usif/format usif/storage usif/properties
python -m bandit -q -r usif -x tests
python -m pip_audit --desc off
python -m build
```

## Documentation map

- `docs/ARCHITECTURE.md` — current architecture overview.
- `docs/BINARY_FORMAT.md` — `.usif` binary format.
- `docs/CONTAINER_FORMAT.md` — `.usifc` container format.
- `docs/PROPERTY_SYSTEM.md` — built-in and custom property model.
- `docs/CONTRIBUTING.md` — local development, testing, and PR expectations.
- `docs/CHANGELOG.md` — notable changes.
- `docs/archive/` — historical reviews and old planning documents.

## License

USIF is licensed under the USIF Non-Commercial License. Academic and non-commercial use is allowed under the license terms. For commercial licensing, contact `haidi@hfut.edu.cn`.
