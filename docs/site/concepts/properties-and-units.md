# Properties and Units

USIF supports structure-level and atom-level scalar, vector, tensor, and custom properties.

```python
from usif import StructureProperties, AtomicProperties

props = StructureProperties()
props.set_scalar("energy", -10.5)                         # default units: eV
props.set_tensor("stress", [[1,0,0],[0,1,0],[0,0,1]])    # default units: GPa
props.set_vector("dipole", [0, 0, 1.2], units="Debye")

atom = AtomicProperties()
atom.set_scalar("charge", -0.25)                         # default units: e
atom.set_vector("force", [0.1, 0, 0], units="eV/Ang")   # canonical: eV/Å
atom.set_tensor("quadrupole", [[1,0,0],[0,1,0],[0,0,1]], units="e Å²")
```

## Unit alias normalization

Unit strings are normalized for convenient Unicode and ASCII input. Values are not automatically converted.

| Input | Canonical |
|---|---|
| `Å²`, `Å^2`, `Ang^2`, `angstrom^2` | `Å^2` |
| `Å³`, `Ang^3`, `angstrom^3` | `Å^3` |
| `eV/Ang` | `eV/Å` |
| `cm⁻¹` | `cm^-1` |
| `g/cm³` | `g/cm^3` |

## PropertyValue envelope

Custom properties can carry metadata:

```python
props.set_vector(
    "dipole",
    [0.0, 0.0, 1.2],
    units="Debye",
    description="molecular dipole moment",
    metadata={"method": "DFT"},
)
```

The value, kind, units, description, and metadata round-trip through `.usif`, `.json`, `.usif.json`, and `.usifc` records.

## Built-in default units

| Property | Level | Default unit |
|---|---|---|
| `energy` | structure | `eV` |
| `volume` | structure | `Å^3` |
| `stress` | structure | `GPa` |
| `pressure` | structure | `GPa` |
| `temperature` | structure | `K` |
| `charge` | atom | `e` |
| `force` | atom | `eV/Å` |
| `velocity` | atom | `Å/fs` |
| `magmom` | atom | `μB` |
