# ASE Interop

ASE import/export requires both ASE and pymatgen. The ASE adapter uses `pymatgen.io.ase.AseAtomsAdaptor` and then delegates to canonical pymatgen adapters.

```python
from usif.interop.ase import ASEImporter, ASEExporter

structure = ASEImporter.from_ase(atoms)
atoms_roundtrip = ASEExporter.to_ase(structure)
```
