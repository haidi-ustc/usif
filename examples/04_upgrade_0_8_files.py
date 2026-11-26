"""Reading and converting files written by USIF 0.8 and earlier.

Format-5/6 records are read transparently (``usif convert old.usif new.usif`` rewrites
one as format 7); v2 containers are imported into a dataset with ``Dataset.import_v2``.
"""

import tempfile
import warnings
from pathlib import Path

import usif
from usif.upgrade import open_container_v2

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

old = usif.read(FIXTURES / "format5" / "rutile_136.usif")
print(f"Format-5 record: {old}")

with open_container_v2(FIXTURES / "format6" / "container_v2.usifc") as container:
    print(f"v2 container entries: {[e.name for e in container]}")

with tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings():
    warnings.simplefilter("ignore")  # one fixture has a partially present per-atom charge
    with usif.Dataset(Path(tmp) / "new.usifc") as dataset:
        imported = dataset.import_v2(FIXTURES / "format6" / "container_v2.usifc")
        print(f"Imported {imported} entries into groups {dataset.groups()}")
        print(f"Validation ok: {dataset.check(full=True).ok}")
