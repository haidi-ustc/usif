"""The ``usif`` command line (run here through ``usif.cli.main``)."""

import os
import tempfile
from pathlib import Path

import usif
from usif.cli import main

home = os.environ.get("USIF_HOME")
with tempfile.TemporaryDirectory() as tmp:
    os.environ["USIF_HOME"] = str(Path(tmp) / "home")  # keep the plan journal out of ~/.usif
    record = Path(tmp) / "nacl.usif"
    usif.write(
        usif.Structure.from_fractional(
            ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], usif.Cell.cubic(5.64)
        ),
        record,
    )
    runs = Path(tmp) / "runs" / "kcl"
    runs.mkdir(parents=True)
    usif.write(
        usif.Structure.from_fractional(
            ["K", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], usif.Cell.cubic(6.29)
        ),
        runs / "relaxed.usif",
    )
    dataset = Path(tmp) / "data.usifc"
    plan = Path(tmp) / "plan.json"
    for argv in (
        ["version"],
        ["inspect", str(record)],
        ["convert", str(record), str(Path(tmp) / "nacl.json")],
        ["dataset", "add", str(dataset), str(record), "--group", "/salts"],
        # Register a project directory: a change plan, applied here with --yes.
        ["dataset", "import", str(runs.parent), str(dataset), "--group", "/runs"]
        + ["--plan-out", str(plan), "--yes"],
        ["agent", "show", str(plan)],
        ["dataset", "list", str(dataset), "--elements", "Cl"],
        ["validate", str(dataset), "--full"],
    ):
        print(f"$ usif {' '.join(argv)}")
        assert main(argv) == 0
if home is None:
    os.environ.pop("USIF_HOME", None)
else:
    os.environ["USIF_HOME"] = home  # restored: runpy runs this inside the test process
