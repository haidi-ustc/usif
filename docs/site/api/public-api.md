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
from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter
from usif.interop.ase import ASEImporter, ASEExporter
```

## Integrations and benchmarks

```python
from usif.integrations.materials_project import load_mp_group, convert_mp_to_usif
from usif.benchmarks import benchmark_compression
```
