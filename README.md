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

## Current 6.1 API boundaries

| Area | Canonical import | Responsibility |
|---|---|---|
| model | `from usif import USIFStructure` | pure structure data, validation, dict round-trip |
| codec | `from usif import USIF` | `.usif` encode/decode/save/load |
| services | `from usif.services import import_structure, save_structure, load_structure` | application import/export, `.usif`, and official JSON workflows |
| container | `from usif.storage import StructureContainer` | `.usifc` multi-record storage, query, groups, validation |
| pymatgen interop | `from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter` | pymatgen adapters |
| ASE interop | `from usif.interop.ase import ASEImporter, ASEExporter` | ASE adapters through canonical pymatgen adapters |
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


## Official JSON structure files

USIF 6.1.0 formally supports human-readable JSON alongside binary `.usif` files. Use `.json` or `.usif.json` with the same service functions:

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
        print(container.validate(decode_records=True).is_valid)
```

Run the complete container example:

```bash
python examples/02_container_write_query_validate.py
```

Container implementation is split across focused modules under `usif.storage`, but the public storage package intentionally exports only `StructureContainer`, `USIFGroup`, and `ContainerValidationResult`. Internal record/index/cache/query modules are imported from their concrete submodules when needed by contributors.

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
version = "6.1.0"

[tool.usif.release]
date = "2026-06-05"
sequence = 4
record = "20260605.004"
id = "usif-20260605-004"
```

`FORMAT_VERSION = 5` is the `.usif` binary record format version and changes only when the binary record layout changes.

## Testing and release workflow

Common local commands:

```bash
black --check usif tests examples
isort --check-only usif tests examples
mypy usif
bandit -q -r usif -x tests
pip_audit
pytest tests/unit
pytest tests/integration tests/reliability tests/examples
```

CI also builds source and wheel artifacts and installs the wheel in a clean virtual environment.

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
