# ASE Interop

Install the `ase` extra (`pip install usif[ase]`). The ASE adapter does not need pymatgen.

```python
from usif.interop.ase import ASEImporter, ASEExporter

structure = ASEImporter.from_ase(atoms)
atoms_roundtrip = ASEExporter.to_ase(structure)
```

Mapping:

- an `Atoms` object with a non-degenerate cell becomes a crystal, otherwise a molecule; partial `pbc` is kept;
- calculator energy, forces, stress, charges and magnetic moments are used when present, otherwise `initial_charges` / `initial_magmoms`;
- stress is converted from eV/Å³ (ASE) to GPa (USIF) and back; velocities are stored in Å/fs;
- other per-atom arrays become per-atom custom values; JSON-compatible `info` entries become structure custom values.

On export, energy, forces and stress are attached through a `SinglePointCalculator`.
