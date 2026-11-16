"""Smallest USIF workflow: build a structure, save it, read it back, store it in a dataset."""

import tempfile
from pathlib import Path

import usif
from usif import Cell, Structure

with tempfile.TemporaryDirectory() as tmp:
    nacl = Structure.from_fractional(
        ["Na", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
        Cell.cubic(5.64),
        properties={"energy": -6.8},
    )
    print(f"Formula: {nacl.reduced_formula}")

    path = Path(tmp) / "nacl.usif"
    usif.write(nacl, path)
    again = usif.read(path)
    print(f"Round trip exact: {again == nacl}")

    with usif.Dataset(Path(tmp) / "data.usifc") as dataset:
        dataset.add(nacl, "nacl", "/salts")
        hits = [entry.path for entry in dataset.query(usif.Q.formula("NaCl"))]
        print(f"Query hits: {hits}")
