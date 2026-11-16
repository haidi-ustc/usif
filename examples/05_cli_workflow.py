"""The ``usif`` command line (run here through ``usif.cli.main``)."""

import tempfile
from pathlib import Path

import usif
from usif.cli import main

with tempfile.TemporaryDirectory() as tmp:
    record = Path(tmp) / "nacl.usif"
    usif.write(
        usif.Structure.from_fractional(
            ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], usif.Cell.cubic(5.64)
        ),
        record,
    )
    dataset = Path(tmp) / "data.usifc"
    for argv in (
        ["version"],
        ["inspect", str(record)],
        ["convert", str(record), str(Path(tmp) / "nacl.json")],
        ["dataset", "add", str(dataset), str(record), "--group", "/salts"],
        ["dataset", "list", str(dataset), "--formula", "NaCl"],
        ["validate", str(dataset), "--full"],
    ):
        print(f"$ usif {' '.join(argv)}")
        assert main(argv) == 0
