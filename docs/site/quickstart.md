# Quickstart

This quickstart creates a pymatgen NaCl structure, imports it into USIF, saves a binary `.usif` file, then loads it back.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from pymatgen.core import Lattice, Structure

from usif.services import import_structure, save_structure, load_structure

pmg = Structure(
    Lattice.cubic(5.64),
    ["Na", "Cl"],
    [[0, 0, 0], [0.5, 0.5, 0.5]],
)

structure = import_structure(pmg, energy=-10.5, calculator="VASP")

with TemporaryDirectory() as tmp:
    path = Path(tmp) / "nacl.usif"
    save_structure(structure, path)
    loaded = load_structure(path)
    print(loaded.formula)
```

Run the repository example:

```bash
python examples/quickstart.py
```

## JSON quickstart

USIF also supports official JSON documents:

```python
from usif.services import save_structure, load_structure

save_structure(structure, "nacl.usif.json")
loaded = load_structure("nacl.usif.json")
```

The JSON schema marker is `usif.structure.json.v1`.

## Container quickstart

```python
from usif.storage import StructureContainer

with StructureContainer("materials.usifc", mode="w") as container:
    container.add(structure, name="nacl", group="/examples/halides")

with StructureContainer("materials.usifc", mode="r") as container:
    print(container.list_formulas())
    print(container.query(formula="NaCl"))
    print(container.validate(level="index").ok)
```
