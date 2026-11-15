# pymatgen Interop

Install the `pymatgen` extra (`pip install usif[pymatgen]`).

```python
from usif.services import import_structure, export_structure

usif_structure = import_structure(pmg_structure, energy=-10.5)
pmg_roundtrip = export_structure(usif_structure, fmt="pymatgen")
```

The adapter lives in `usif.interop.pymatgen` and converts through the backend-neutral array layer in `usif.interop.common`:

- site properties `forces`, `charge`, `magmom` and `velocities` become per-atom properties; other site properties become per-atom custom values;
- oxidation states (`Species`) and molecule `charge` / `spin_multiplicity` are kept as custom values and restored on export;
- disordered (partially occupied) structures are rejected with `ValidationError`.
