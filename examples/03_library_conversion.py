"""Converting to and from matsimpy, ASE and pymatgen (each one is optional)."""

import importlib.util

import numpy as np

import usif
from usif import Cell, Structure

rng = np.random.default_rng(1)
structure = Structure.from_fractional(
    ["Si", "Si"],
    [[0, 0, 0], [0.25, 0.25, 0.25]],
    Cell([[0, 2.715, 2.715], [2.715, 0, 2.715], [2.715, 2.715, 0]]),
    arrays={"force": rng.normal(scale=0.01, size=(2, 3))},
    properties={"energy": -10.84, "stress": np.zeros(6)},
)

for library in ("matsimpy", "ase", "pymatgen"):
    if importlib.util.find_spec(library) is None:
        print(f"{library}: not installed, skipped")
        continue
    obj = usif.convert(structure, library)  # Structure -> library object
    back = usif.convert(obj)  # library object -> Structure
    print(f"{library}: {type(obj).__name__}, exact round trip: {back == structure}")

if importlib.util.find_spec("ase") is not None:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        usif.write(structure, Path(tmp) / "si.extxyz")  # any backend format by suffix
        print(f"extxyz keeps forces: {'force' in usif.read(Path(tmp) / 'si.extxyz').arrays}")
