# Public API Map

Stable public APIs follow `docs/API_STABILITY.md`.

## Core

```python
from usif import USIF, USIFStructure, StructureProperties, AtomicProperties
```

## Services

```python
from usif.services import import_structure, export_structure, save_structure, load_structure
from usif.services import save_structure_json, load_structure_json
```

## Containers

```python
from usif.storage import StructureContainer, USIFGroup, ContainerValidationResult
```

## Interop

```python
from usif.interop.common import build_structure, structure_to_arrays  # no backend needed
from usif.interop.matsimpy import MatsimpyImporter, MatsimpyExporter    # usif[matsimpy]
from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter    # usif[pymatgen]
from usif.interop.ase import ASEImporter, ASEExporter                   # usif[ase]
from usif.symmetry import SymmetryPolicy, apply_symmetry_policy
```

## Integrations and benchmarks

```python
from usif.integrations.materials_project import load_mp_group, convert_mp_to_usif
from usif.benchmarks import benchmark_compression
```


## Command-line interface

The stable CLI entry point is:

```bash
usif version
usif inspect structure.usif
usif convert structure.usif structure.usif.json
usif validate dataset.usifc --level full
usif container stats dataset.usifc
```

Programmatic callers may invoke the Typer-backed `from usif.cli import main`, but library code should prefer the service and storage APIs directly.
