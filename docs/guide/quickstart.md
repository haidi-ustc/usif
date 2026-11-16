# Quickstart

## Install

```bash
pip install usif              # core: numpy, spglib, typer
pip install "usif[ase]"       # optional: ASE objects and file formats
```

See the [README](../../README.md#installation) for all extras.

## Build a structure

```python
import numpy as np
import usif
from usif import Cell, Structure

nacl = Structure.from_fractional(
    ["Na", "Cl"],
    [[0, 0, 0], [0.5, 0.5, 0.5]],
    Cell.cubic(5.64),
    properties={"energy": -6.8},
)
nacl.arrays["force"] = np.zeros((2, 3))
print(nacl)                       # Structure(NaCl, natoms=2, periodic, arrays=['force'], properties=['energy'])
print(nacl.properties.units())    # {'energy': 'eV'}
print(nacl.arrays.unit("force"))  # eV/Å
```

A molecule has no cell: `Structure(["O", "H", "H"], positions)`. See [Structures](structures.md) and [Properties and units](properties.md).

## Save and load

```python
usif.write(nacl, "nacl.usif")                     # binary record, float64, zlib
usif.write(nacl, "nacl.json")                     # JSON document
usif.write(nacl, "small.usif", precision="f32", compression="lzma")

assert usif.read("nacl.usif") == nacl             # exact
assert usif.read("nacl.json") == nacl             # exact
assert usif.read("small.usif").allclose(nacl, atol=1e-5)
```

`usif.read` and `usif.write` choose the format by suffix: `.usif` and `.json`/`.usif.json` are native ([Records and JSON](records.md)); any other suffix goes to the first installed backend (matsimpy, ASE, pymatgen) that can handle it.

## Store many structures

```python
from usif import Dataset, Q

with Dataset("data.usifc") as ds:
    for a in (5.5, 5.6, 5.7):
        s = Structure.from_fractional(
            ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(a),
            properties={"energy": 0.5 * (a - 5.64) ** 2 - 6.8},
        )
        ds.add(s, f"a={a}", "/eos", attrs={"method": "PBE"})

with Dataset("data.usifc", "r") as ds:
    for entry in ds.query(Q.group("/eos") & (Q.prop("energy") < -6.79)):
        print(entry.path, entry.structure.properties["energy"])
```

See [Datasets](datasets.md).

## Convert to other libraries

```python
atoms = usif.convert(nacl, "ase")     # needs usif[ase]
back = usif.convert(atoms)            # any supported library object -> Structure
assert back == nacl
```

See [Other libraries](libraries.md).

## Next

- [Command line](command-line.md)
- [Upgrading USIF 0.8 files](upgrading.md)
- [Public API](api.md)
- Runnable scripts: [`examples/`](../../examples/README.md), starting with [`examples/quickstart.py`](../../examples/quickstart.py)
