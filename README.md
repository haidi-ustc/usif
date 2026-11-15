# USIF — Universal Structure Interchange Format

USIF is a Python 3.10+ library for representing, converting, encoding, and grouping atomistic structures. It supports crystals and molecules, compact symmetry-aware storage, explicit full-atom storage with per-atom properties, binary `.usif` files, and multi-structure `.usifc` containers.

```python
from usif.services import import_structure, load_structure, save_structure

structure = import_structure("NaCl.cif", energy=-10.5, calculator="VASP")  # any installed backend
save_structure(structure, "nacl.usif")
loaded = load_structure("nacl.usif")
print(loaded.formula)
```

## Current 0.8 API boundaries

| Area | Canonical import | Responsibility |
|---|---|---|
| model | `from usif import USIFStructure` | pure structure data, validation, dict round-trip |
| codec | `from usif import USIF` | `.usif` encode/decode/save/load |
| services | `from usif.services import import_structure, save_structure, load_structure` | application import/export, `.usif`, and official JSON workflows |
| container | `from usif.storage import StructureContainer` | `.usifc` multi-record storage, query, groups, validation |
| array layer | `from usif.interop.common import build_structure, structure_to_arrays` | backend-free construction and export (numpy arrays) |
| matsimpy interop | `from usif.interop.matsimpy import MatsimpyImporter, MatsimpyExporter` | optional matsimpy adapters |
| pymatgen interop | `from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter` | optional pymatgen adapters |
| ASE interop | `from usif.interop.ase import ASEImporter, ASEExporter` | optional ASE adapters (no pymatgen needed) |
| symmetry | `from usif.symmetry import SymmetryPolicy, apply_symmetry_policy` | spglib-based lossless symmetric storage |
| properties | `from usif import PropertyDefinition, create_default_registry` | property definitions, validation, binary serialization |
| benchmarks | `from usif.benchmarks import benchmark_compression` | optional encode/decode compression benchmarks |
| Materials Project | `from usif.integrations.materials_project import ...` | optional MP download/load/map/archive tooling |
| CLI | `usif ...` / `from usif.cli import main` | version, inspect, convert, validate, and container operations |

The core needs only `numpy` and `spglib`. matsimpy, pymatgen and ASE are independent optional backends: each adapter converts through the same backend-neutral array layer, so the same structure produces the same record whichever library it came from.

`USIFStructure` is intentionally a pure model. It does not provide `from_source()`, `from_pymatgen()`, `to()`, `save()`, or `load()`. Use `usif.services` or explicit interop/codec classes at application boundaries.


## Documentation site

USIF 0.8.0 includes a productized plain-Markdown documentation site under `docs/site/`. Start with:

- `docs/site/index.md`
- `docs/site/quickstart.md`
- `docs/site/concepts/properties-and-units.md`
- `docs/site/tutorials/container-workflow.md`
- `docs/site/api/public-api.md`

The root README remains the quick entry point; the site contains the complete concepts, tutorials, cookbook recipes, and API map.

## Installation

From a source checkout:

```bash
python -m pip install -e .                    # core: numpy + spglib
python -m pip install -e ".[dev,pymatgen,ase]"
python -m pip install -e ".[all]"  # includes Materials Project tooling
```

Runtime dependencies are declared in `pyproject.toml`: `numpy`, `spglib`, `typer`, and `tomli` on Python 3.10. Optional extras are:

| Extra | Purpose |
|---|---|
| `matsimpy` | matsimpy `Crystal`/`Molecule` import/export and file I/O. matsimpy is not on PyPI: install it from its source checkout (`pip install -e /path/to/matsimpy`) |
| `pymatgen` | pymatgen `Structure`/`Molecule` import/export and file I/O |
| `ase` | ASE `Atoms` import/export and file I/O |
| `mp` | Materials Project API download tooling (also installs `monty`) |
| `benchmark` | benchmark helper dependencies |
| `dev` | tests, lint, type checks, security checks, build |
| `all` | all optional dependencies |


## Command-line interface

USIF 0.8.0 adds an official Typer-powered `usif` console script. It is designed for quick file inspection, conversion, validation, and container operations without writing a Python script.

```bash
usif version
usif inspect nacl.usif
usif convert nacl.usif nacl.usif.json
usif validate nacl.usif.json
usif container stats materials.usifc
usif container list materials.usifc formulas
usif container query materials.usifc --formula NaCl --has-property energy
```

All inspection and query commands support `--json` for machine-readable output, which makes the CLI suitable for shell pipelines and CI smoke tests.

## Quick start

```python
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from usif.interop.common import build_structure
from usif.services import load_structure, save_structure

with TemporaryDirectory() as tmp:
    structure = build_structure(
        [11, 17],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
        lattice=np.eye(3) * 5.64,
        cartesian=False,
        energy=-10.5,
        custom={"calculator": "VASP"},
    )
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

USIF 0.8.0 provides shape-aware property helpers for structure-level and atom-level values:

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


USIF 0.8.0 keeps `PropertySerializer` as the stable public facade while splitting the implementation into focused modules under `usif.properties.serializers`. This makes scalar, vector, tensor, JSON-safe custom values, validation, and size estimation easier to test and maintain without changing user-facing property APIs.

USIF 0.8.0 also stores unit metadata for built-in and custom properties. Unit strings are normalized but values are not automatically converted: `Å²`, `Å^2`, `Ang^2`, and `angstrom^2` all store as `Å^2`; `eV/Ang` stores as `eV/Å`. Use `get_units(name)` to read canonical unit metadata.

## Official JSON structure files

USIF 0.8.0 formally supports human-readable JSON alongside binary `.usif` files. Use `.json` or `.usif.json` with the same service functions:

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

import numpy as np

from usif.interop.common import build_structure
from usif.storage import StructureContainer

def nacl(energy):
    return build_structure(
        [11, 17], [[0, 0, 0], [0.5, 0.5, 0.5]], lattice=np.eye(3) * 5.64, cartesian=False, energy=energy
    )

low = nacl(-10.5)
high = nacl(-10.0)

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

USIF 0.8.0 persists formula, geometry, and property secondary indexes inside the `.usifc` index generation. Opening a large container no longer needs to decode every record just to query by formula, property, group, or geometry. Validation is explicit and cost-aware: `validate(level="index")` checks metadata only, `validate(level="records")` verifies byte ranges and USIF record headers, and `validate(level="full")` decodes every structure and verifies record hashes.

## Conversion with matsimpy, pymatgen and ASE

`import_structure()` accepts a file path or a matsimpy, pymatgen or ASE object; `export_structure(..., fmt=...)` returns one. Non-USIF files (CIF, POSCAR, XYZ, ...) are read and written with the first installed backend, tried in the order matsimpy, ASE, pymatgen.

```python
import matsimpy

from usif.services import export_structure, import_structure
from usif.symmetry import SymmetryPolicy

crystal = matsimpy.Crystal(
    ["Na", "Cl"], [[0, 0, 0], [2.82, 2.82, 2.82]],
    matsimpy.Lattice([[5.64, 0, 0], [0, 5.64, 0], [0, 0, 5.64]]),
    coords_are_cartesian=True,
)
structure = import_structure(crystal, energy=-10.5, symmetry_policy=SymmetryPolicy(mode="analyze"))
round_tripped = export_structure(structure, fmt="matsimpy")
arrays = export_structure(structure, fmt="arrays")  # backend-free AtomsData
```

With pymatgen:

```python
from pymatgen.core import Lattice, Structure

pmg = Structure(Lattice.cubic(5.64), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
structure = import_structure(pmg, energy=-10.5)
round_tripped = export_structure(structure, fmt="pymatgen")
print(round_tripped.composition.reduced_formula)
```

Symmetric storage is lossless: a structure is stored as space-group representatives only when spglib finds a setting whose expansion reproduces every atom within 1e-5 Å, otherwise it stays full-atomic. pymatgen oxidation states, molecule charge and spin multiplicity are preserved; disordered structures are rejected.

Or use adapters directly:

```python
from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter

structure = PymatgenImporter.from_pymatgen(pmg)
round_tripped = PymatgenExporter.to_pymatgen(structure)
```

ASE support requires only the `ase` extra (stress is converted from eV/Å³ to GPa):

```python
from ase import Atoms
from usif.services import import_structure

atoms = Atoms("H2O", positions=[[0, 0, 0], [0.95, 0, 0], [0.95, 0.95, 0]])
water = import_structure(atoms, energy=-76.4)
print(water.formula)
```

Run the complete examples:

```bash
python examples/12_matsimpy_conversion_roundtrip.py   # needs matsimpy
python examples/03_pymatgen_conversion_roundtrip.py   # needs pymatgen
python examples/05_symmetry_policy_import.py          # core only
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
python examples/10_materials_project_dataset.py --help
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
version = "0.8.0"

[tool.usif.release]
date = "2026-11-15"
sequence = 17
record = "20261115.017"
id = "usif-20261115-017"
```

`FORMAT_VERSION = 6` is the `.usif` binary record format version and changes only when the binary record layout changes. See `docs/FORMAT_VERSIONING.md` for the distinction between package versions, date-based release records, `.usif` record format versions, and `.usifc` container metadata. See `docs/API_STABILITY.md` for the 0.8.x public API stability policy.

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
python examples/10_materials_project_dataset.py --help
```

### Container introspection and enhanced query filters

USIF 0.8.0 adds lightweight container introspection APIs that use persisted
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
