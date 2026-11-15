# matsimpy Interop

matsimpy is an optional backend. It is not published on PyPI; install it from its source checkout (`pip install -e /path/to/matsimpy`).

```python
import matsimpy

from usif.services import export_structure, import_structure

crystal = matsimpy.Crystal(
    ["Na", "Cl"],
    [[0, 0, 0], [2.82, 2.82, 2.82]],
    matsimpy.Lattice([[5.64, 0, 0], [0, 5.64, 0], [0, 0, 5.64]]),
    coords_are_cartesian=True,
    metadata={"energy": -10.5},
)
structure = import_structure(crystal)
roundtrip = export_structure(structure, fmt="matsimpy")
```

Mapping:

- `Crystal` becomes a USIF crystal, `Molecule` a USIF molecule;
- per-site keys `force`/`forces`, `charge`, `magmom` and `velocity`/`velocities` become per-atom properties; other keys become per-atom custom values;
- `metadata` entries `energy` and `stress` (GPa) become structure properties; other JSON-compatible entries become structure custom values.

When matsimpy is installed it is also the first backend tried for reading and writing CIF, POSCAR, XYZ and other non-USIF files.

See `examples/12_matsimpy_conversion_roundtrip.py`.
