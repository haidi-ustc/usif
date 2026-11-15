# Quickstart

This quickstart builds a NaCl structure from arrays (no optional backend needed), saves a binary `.usif` file, then loads it back. With matsimpy, pymatgen or ASE installed, `import_structure()` also accepts their objects or a CIF/POSCAR/XYZ path.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from usif.interop.common import build_structure
from usif.services import save_structure, load_structure

structure = build_structure(
    [11, 17],
    [[0, 0, 0], [0.5, 0.5, 0.5]],
    lattice=np.eye(3) * 5.64,
    cartesian=False,
    energy=-10.5,
    custom={"calculator": "VASP"},
)

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
