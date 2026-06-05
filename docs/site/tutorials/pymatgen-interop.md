# pymatgen Interop

```python
from usif.services import import_structure, export_structure

usif_structure = import_structure(pmg_structure, energy=-10.5)
pmg_roundtrip = export_structure(usif_structure, fmt="pymatgen")
```

The adapter contract is implemented under `usif.interop.pymatgen`.
