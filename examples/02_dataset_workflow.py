"""Datasets: deduplicated storage, groups, attributes, links, queries, integrity checks."""

import tempfile
from pathlib import Path

import numpy as np

from usif import Cell, Dataset, Q, Structure


def rocksalt(a: float, energy: float) -> Structure:
    return Structure.from_fractional(
        ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(a), properties={"energy": energy}
    )


with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "scan.usifc"
    with Dataset(path, symmetry="auto") as dataset:
        # An equation-of-state scan: one group, one entry per lattice constant.
        lattice = np.linspace(5.4, 5.9, 11)
        energies = 0.5 * (lattice - 5.64) ** 2 - 6.8
        dataset.add_many(
            (rocksalt(a, e) for a, e in zip(lattice, energies)),
            "/eos",
            names=[f"a={a:.2f}" for a in lattice],
            attrs={"method": "PBE"},
        )
        dataset.set_group_attrs("/eos", {"description": "NaCl equation of state"})

        # Adding identical content again stores no new record.
        dataset.add(rocksalt(lattice[5], energies[5]), "reference", "/ref", attrs={"note": "copy"})
        stats = dataset.stats()
        print(f"Entries: {stats['entries']}, records: {stats['records']}")

        # Queries combine record conditions and entry conditions.
        low = Q.group("/eos") & (Q.prop("energy") < -6.79)
        print(f"Near the minimum: {[e.name for e in dataset.query(low)]}")
        print(f"Contains Na and Cl: {dataset.count(Q.elements('Na', 'Cl'))}")
        print(f"PBE entries: {dataset.count(Q.attr('method') == 'PBE')}")

        # One structure in a second group: link() shares the record, nothing is copied.
        dataset.link("/eos/a=5.65", "minimum", "/projects/eos", {"selected": True})
        stats = dataset.stats()
        print(f"After link: {stats['entries']} entries, {stats['records']} records")

        structure = dataset["/eos/a=5.65"]
        print(f"Loaded: {structure} energy={structure.properties['energy']:.4f}")

        dataset.remove("/ref/reference")
        print(f"Validation ok: {dataset.check(full=True).ok}")
        print(f"Bytes reclaimed by compact: {dataset.compact() >= 0}")

    # Several processes may read while one writes.
    with Dataset(path, "r") as reader:
        print(f"Read-only entries: {len(reader)}")
