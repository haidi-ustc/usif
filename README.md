# USIF — Universal Structure Interchange Format

USIF is a Python 3.10+ library for representing, converting, encoding, and grouping atomistic structures. It supports crystals and molecules, compact symmetry-aware storage, explicit full-atom storage with per-atom properties, binary `.usif` files, and multi-structure `.usifc` containers.

```python
from pymatgen.core import Lattice, Structure
from usif.services import import_structure, load_structure, save_structure

pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
structure = import_structure(pmg, energy=-10.5, calculator="VASP")
save_structure(structure, "nacl.usif")
loaded = load_structure("nacl.usif")
print(loaded.formula)
```

## Current 6.6 API boundaries

| Area | Canonical import | Responsibility |
|---|---|---|
| model | `from usif import USIFStructure` | pure structure data, validation, dict round-trip |
| codec | `from usif import USIF` | `.usif` encode/decode/save/load |
| services | `from usif.services import import_structure, save_structure, load_structure` | application import/export, `.usif`, and official JSON workflows |
| container | `from usif.storage import StructureContainer` | `.usifc` multi-record storage, query, groups, validation |
| pymatgen interop | `from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter` | pymatgen adapters |
| ASE interop | `from usif.interop.ase import ASEImporter, ASEExporter` | ASE adapters through canonical pymatgen adapters |

ASE support requires both ASE and pymatgen. The ASE adapter depends on pymatgen because it uses `pymatgen.io.ase.AseAtomsAdaptor` before delegating to the canonical pymatgen adapters.
| properties | `from usif import PropertyDefinition, create_default_registry` | property definitions, validation, binary serialization |
| benchmarks | `from usif.benchmarks import benchmark_compression` | optional encode/decode compression benchmarks |
| Materials Project | `from usif.integrations.materials_project import ...` | optional MP download/load/map/archive tooling |

`USIFStructure` is intentionally a pure model. It does not provide `from_source()`, `from_pymatgen()`, `to()`, `save()`, or `load()`. Use `usif.services` or explicit interop/codec classes at application boundaries.

## Installation

From a source checkout:

```bash
python -m pip install -e ".[dev,ase]"
python -m pip install -e ".[all]"  # includes Materials Project tooling
```

Runtime dependencies are declared in `pyproject.toml`: `numpy`, `pymatgen`, `monty`, and `tomli` on Python 3.10. Optional extras are:

| Extra | Purpose |
|---|---|
| `ase` | ASE `Atoms` import/export |
| `mp` | Materials Project API download tooling |
| `benchmark` | benchmark helper dependencies |
| `dev` | tests, lint, type checks, security checks, build |
| `all` | all optional dependencies |

## Quick start

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from pymatgen.core import Lattice, Structure

from usif.services import import_structure, load_structure, save_structure

with TemporaryDirectory() as tmp:
    pmg = Structure(
        Lattice.cubic(5.64),
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )
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

## Manual structure creation and binary round-trip

```python
import numpy as np

from usif import (
    CompressionType,
    StructureProperties,
    StructureType,
    StorageMode,
    USIF,
    USIFStructure,
    WyckoffSite,
)

structure = USIFStructure(
    structure_type=StructureType.CRYSTAL,
    storage_mode=StorageMode.SYMMETRIC,
    lattice_matrix=np.eye(3) * 5.64,
    spacegroup=225,
    wyckoff_sites=[
        WyckoffSite(11, 4, (0, 0, 0)),
        WyckoffSite(17, 4, (0.5, 0.5, 0.5)),
    ],
    structure_properties=StructureProperties(energy=-10.5),
    formula="NaCl",
)

codec = USIF(compression=CompressionType.GZIP)
data = codec.encode(structure)
decoded, geometry_hash = codec.decode(data)
print(decoded.formula, geometry_hash.hex())
```

Run the complete example:

```bash
python examples/01_manual_structure_binary_roundtrip.py
```



## Property management

USIF 6.8.0 provides shape-aware property helpers for structure-level and atom-level values:

```python
from usif import AtomicProperties, StructureProperties

props = StructureProperties()
props.set_scalar("energy", -10.5)  # default units: eV
props.set_tensor("stress", [[1, 0, 0], [0, 1, 0], [0, 0, 1]], units="GPa")
props.set_vector("dipole", [0.0, 0.0, 1.2], units="Debye")
props.set_tensor("quadrupole", [[1, 0, 0], [0, 1, 0], [0, 0, 1]], units="Ang^2")
props.set_custom("calculation", {"code": "example", "converged": True})

atom = AtomicProperties()
atom.set_scalar("charge", -0.25)  # default units: e
atom.set_vector("force", [0.1, 0.0, 0.0], units="eV/Ang")
atom.set_tensor("quadrupole", [[1, 0, 0], [0, 1, 0], [0, 0, 1]], units="e Å²")
```

For full-atomic structures, atom-aligned updates are available directly on the pure model:

```python
structure.set_structure_property("energy", -10.5)
structure.set_atomic_property("charge", [1.0, -1.0])
structure.set_atomic_property("force", [[0, 0, 0], [0.1, 0, 0]])
structure.set_atom_property(1, "site_label", "Cl1")
```

Custom values are normalized to JSON-compatible scalars, lists, dictionaries, booleans, and `None`, so they round-trip through binary `.usif`, JSON `.json` / `.usif.json`, and container `.usifc` records.


USIF 6.8.0 keeps `PropertySerializer` as the stable public facade while splitting the implementation into focused modules under `usif.properties.serializers`. This makes scalar, vector, tensor, JSON-safe custom values, validation, and size estimation easier to test and maintain without changing user-facing property APIs.

USIF 6.8.0 also stores unit metadata for built-in and custom properties. Unit strings are normalized but values are not automatically converted: `Å²`, `Å^2`, `Ang^2`, and `angstrom^2` all store as `Å^2`; `eV/Ang` stores as `eV/Å`. Use `get_units(name)` to read canonical unit metadata.

## Official JSON structure files

USIF 6.8.0+ formally supports human-readable JSON alongside binary `.usif` files. Use `.json` or `.usif.json` with the same service functions:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from usif import StructureProperties, StructureType, StorageMode, USIFStructure, WyckoffSite
from usif.services import load_structure, save_structure, structure_to_json_dict

structure = USIFStructure(
    structure_type=StructureType.CRYSTAL,
    storage_mode=StorageMode.SYMMETRIC,
    lattice_matrix=np.eye(3) * 5.64,
    spacegroup=225,
    wyckoff_sites=[WyckoffSite(11, 4, (0, 0, 0)), WyckoffSite(17, 4, (0.5, 0.5, 0.5))],
    structure_properties=StructureProperties(energy=-10.5, custom={"relaxed": True}),
    formula="NaCl",
)

with TemporaryDirectory() as tmp:
    path = Path(tmp) / "nacl.usif.json"
    save_structure(structure, path)
    loaded = load_structure(path)
    print(structure_to_json_dict(loaded)["@schema"])
```

The JSON schema marker is `usif.structure.json.v1`. JSON files preserve standard JSON types such as strings, numbers, booleans, `null`, lists, and dictionaries. Non-finite floating-point values are rejected because they are not valid interoperable JSON.

Run the complete JSON example:

```bash
python examples/06_json_structure_roundtrip.py
```

## Containers

`StructureContainer` stores complete `.usif` records in a `.usifc` file. Records are deduplicated by `record_hash`, while `geometry_hash` groups records that share geometry but differ in properties.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from pymatgen.core import Lattice, Structure

from usif.services import import_structure
from usif.storage import StructureContainer

pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
low = import_structure(pmg, energy=-10.5)
high = import_structure(pmg, energy=-10.0)

with TemporaryDirectory() as tmp:
    path = Path(tmp) / "materials.usifc"
    with StructureContainer(path, mode="w") as container:
        low_hash = container.add(low, name="nacl-low", group="/crystals/halides")
        high_hash = container.add(high, name="nacl-high", group="/crystals/halides")
        print(low_hash != high_hash)
    with StructureContainer(path, mode="r") as container:
        print(container.query(formula="NaCl", energy_range=(-10.6, -10.1)))
        print(container.validate(level="full").ok)
```

Run the complete container example:

```bash
python examples/02_container_write_query_validate.py
```

Container implementation is split across focused modules under `usif.storage`, but the public storage package intentionally exports only `StructureContainer`, `USIFGroup`, and `ContainerValidationResult`. Internal record/index/cache/query modules are imported from their concrete submodules when needed by contributors.

USIF 6.8.0 persists formula, geometry, and property secondary indexes inside the `.usifc` index generation. Opening a large container no longer needs to decode every record just to query by formula, property, group, or geometry. Validation is explicit and cost-aware: `validate(level="index")` checks metadata only, `validate(level="records")` verifies byte ranges and USIF record headers, and `validate(level="full")` decodes every structure and verifies record hashes.

## Conversion with pymatgen and ASE

Use services for application code:

```python
from pymatgen.core import Lattice, Structure

from usif.interop.pymatgen import SymmetryPolicy
from usif.services import export_structure, import_structure

pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
structure = import_structure(pmg, energy=-10.5, symmetry_policy=SymmetryPolicy(mode="analyze"))
round_tripped = export_structure(structure, "pymatgen")
print(round_tripped.composition.reduced_formula)
```

Or use adapters directly:

```python
from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter

structure = PymatgenImporter.from_pymatgen(pmg)
round_tripped = PymatgenExporter.to_pymatgen(structure)
```

ASE support requires the `ase` extra:

```python
from ase import Atoms
from usif.services import import_structure

atoms = Atoms("H2O", positions=[[0, 0, 0], [0.95, 0, 0], [0.95, 0.95, 0]])
water = import_structure(atoms, energy=-76.4)
print(water.formula)
```

Run the complete pymatgen example:

```bash
python examples/03_pymatgen_conversion_roundtrip.py
python examples/05_symmetry_policy_import.py
```

## Properties and hashes

USIF separates structure properties from atom properties:

```python
from usif import AtomicProperties, AtomSite, StructureProperties

atom = AtomSite(3, (0, 0, 0), AtomicProperties(force=(0, 0, 0), charge=0.0))
props = StructureProperties(energy=-1.0, custom={"phase": "bcc-like"})
```

Hash semantics are intentionally separate:

| Helper | Purpose |
|---|---|
| `USIF.get_geometry_hash()` | geometry-only identity used for grouping and `.usif` header integrity |
| `USIF.get_record_hash()` | complete logical record identity, including formula and properties |
| `calculate_payload_digest()` | raw byte digest helper for payload checks |

Run the complete property/hash example:

```bash
python examples/04_properties_and_hashes.py
```

## Materials Project integration

Materials Project helpers live under `usif.integrations.materials_project` and are optional:

```bash
python -m pip install -e ".[mp]"
export MP_API_KEY="your_key_here"
python examples/download_mp_data.py --total_entries 100 --entries_per_group 25
python examples/download_mp_data.py --help
```

Prefer the `MP_API_KEY` environment variable over command-line API keys because shell history and process listings may expose arguments.

Programmatic local data loading:

```python
from usif.integrations.materials_project import load_mp_group, convert_mp_to_usif

docs = load_mp_group("data/mp_structures/group_01/materials.json")
structure = convert_mp_to_usif(docs[0])
```

## Version and release record

`pyproject.toml` is the single editable source for packaging version and dated release metadata:

```toml
[project]
version = "6.8.0"

[tool.usif.release]
date = "2026-06-05"
sequence = 12
record = "20260605.013"
id = "usif-20260605-013"
```

`FORMAT_VERSION = 5` is the `.usif` binary record format version and changes only when the binary record layout changes. See `docs/FORMAT_VERSIONING.md` for the distinction between package versions, date-based release records, `.usif` record format versions, and `.usifc` container metadata. See `docs/API_STABILITY.md` for the 6.x public API stability policy.

## Testing and release workflow

Common local commands:

```bash
black --check usif tests examples
isort --check-only usif tests examples
mypy usif
bandit -q -r usif -x tests
pip_audit
python scripts/check_release_metadata.py
pytest tests/unit
pytest tests/integration tests/reliability tests/examples
```

CI also validates release metadata, builds source and wheel artifacts, and installs the wheel in a clean virtual environment. Release artifacts can include `release-checks.txt` generated by `python scripts/check_release_metadata.py --write-report release-checks.txt`.

## Repository examples

```bash
python examples/quickstart.py
python examples/01_manual_structure_binary_roundtrip.py
python examples/02_container_write_query_validate.py
python examples/03_pymatgen_conversion_roundtrip.py
python examples/04_properties_and_hashes.py
python examples/05_symmetry_policy_import.py
python examples/download_mp_data.py --help
```

### Container introspection and enhanced query filters

USIF 6.8.0 adds lightweight container introspection APIs that use persisted
indexes instead of decoding every record:

```python
with StructureContainer("materials.usifc", mode="r") as container:
    print(container.list_formulas())
    print(container.list_properties())
    print(container.list_groups())
    print(container.stats()["records"])

    stable = container.query(property_range=("energy", -20.0, -5.0))
    tagged = container.query(custom={"metadata.family": "hydride"})
```
