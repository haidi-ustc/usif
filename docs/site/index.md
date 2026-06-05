# USIF Documentation Site

USIF 7.1.0 is a Python 3.10+ toolkit for atomistic structure interchange. It provides a pure structure model, binary `.usif` records, multi-structure `.usifc` containers, official JSON documents, property and unit metadata, pymatgen/ASE adapters, Materials Project integration, an official CLI, and release-governed documentation.

This `docs/site/` tree is the user-facing documentation source. It is intentionally plain Markdown so it can be rendered by MkDocs, Sphinx, GitHub Pages, or any static site generator without changing the package.

## Start here

1. [Quickstart](quickstart.md)
2. [Structure model concepts](concepts/structure-model.md)
3. [Property and unit system](concepts/properties-and-units.md)
4. [Binary `.usif` format](concepts/binary-format.md)
5. [Container `.usifc` format](concepts/container-format.md)
6. [Tutorials](tutorials/README.md)
7. [Cookbook](cookbook/README.md)
8. [Public API map](api/public-api.md)

## Canonical imports

```python
from usif import USIF, USIFStructure, StructureProperties, AtomicProperties
from usif.services import import_structure, save_structure, load_structure
from usif.storage import StructureContainer
from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter
from usif.interop.ase import ASEImporter, ASEExporter
```

USIFStructure is a pure model. `USIFStructure` is the pure model boundary. Import/export, file I/O, and external-library conversion live at service or adapter boundaries.

## Current release

- Package version: `7.1.0`
- Release record: `20260605.016`
- Release ID: `usif-20260605-016`
- `.usif` binary record `FORMAT_VERSION`: `5`

## Documentation map

| Area | Document |
|---|---|
| Quick usage | `quickstart.md` |
| Model design | `concepts/structure-model.md` |
| Properties and units | `concepts/properties-and-units.md` |
| Binary records | `concepts/binary-format.md` |
| Multi-record containers | `concepts/container-format.md` |
| Tutorials | `tutorials/*.md` |
| Recipes | `cookbook/*.md` |
| API surface | `api/public-api.md` |


## CLI quick commands

```bash
usif version
usif inspect nacl.usif
usif convert nacl.usif nacl.usif.json
usif validate nacl.usif.json
usif container stats materials.usifc
```
