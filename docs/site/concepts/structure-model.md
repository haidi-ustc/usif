# Structure Model

`USIFStructure` is the pure in-memory model for crystals and molecules. It stores structure type, storage mode, lattice, sites, properties, formula, and optional symmetry metadata.

## Design rule

The model does not perform file I/O or external library conversion. These operations live in:

- `usif.services` for application-level import/export/save/load;
- `usif.interop.common` for backend-free construction from and export to numpy arrays;
- `usif.interop.matsimpy`, `usif.interop.pymatgen` and `usif.interop.ase` for optional library conversion;
- `usif.symmetry` for spglib-based symmetry reduction and expansion;
- `usif.encoder.USIF` for binary `.usif` records.

## Storage modes

| Mode | Meaning |
|---|---|
| `SYMMETRIC` | symmetry-aware crystal storage using representative sites |
| `FULL` | explicit atom/site storage |
| `MOLECULAR` | molecular storage with point-group metadata when available |

## Pure-model helpers

The model has property helpers that do not cross I/O boundaries:

```python
structure.set_structure_property("energy", -10.5)
structure.set_atomic_property("charge", [1.0, -1.0])
structure.set_atom_property(0, "site_label", "Na1")
```

These helpers operate on `StructureProperties` and `AtomicProperties` only.
