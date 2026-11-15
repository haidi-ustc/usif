#!/usr/bin/env python3
"""Write several structures to a .usifc container, query them, and validate it."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from usif import USIF  # noqa: E402
from usif.interop.common import build_structure  # noqa: E402
from usif.storage import StructureContainer  # noqa: E402


def make_nacl(energy: float):
    return build_structure(
        [11, 17],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
        lattice=np.eye(3) * 5.64,
        cartesian=False,
        energy=energy,
        custom={"calculator": "example"},
    )


def make_li(energy: float):
    return build_structure(
        [3],
        [[0, 0, 0]],
        lattice=np.eye(3) * 3.0,
        cartesian=False,
        energy=energy,
        custom={"calculator": "example"},
    )


def main() -> None:
    with TemporaryDirectory() as tmp:
        container_path = Path(tmp) / "example_materials.usifc"
        low_energy_nacl = make_nacl(-10.5)
        high_energy_nacl = make_nacl(-10.0)
        lithium = make_li(-1.0)

        with StructureContainer(container_path, mode="w") as container:
            low_hash = container.add(
                low_energy_nacl,
                name="nacl-low-energy",
                group="/crystals/halides",
                attributes={"source": "example", "rank": 1},
            )
            high_hash = container.add(
                high_energy_nacl,
                name="nacl-high-energy",
                group="/crystals/halides",
                attributes={"source": "example", "rank": 2},
            )
            container.add(lithium, name="li-metal", group="/crystals/metals")
            geometry_hash = USIF().get_geometry_hash(low_energy_nacl)
            same_geometry = container.get_by_geometry_hash(geometry_hash)
            print(f"Record hashes differ: {low_hash != high_hash}")
            print(f"Same-geometry records before close: {len(same_geometry)}")

        with StructureContainer(container_path, mode="r") as container:
            halides = container.query(group="/crystals/halides")
            stable_nacl = container.query(formula="NaCl", energy_range=(-10.6, -10.1))
            validation = container.validate(level="full")
            print(f"Halide query count: {len(halides)}")
            print(f"Stable NaCl query count: {len(stable_nacl)}")
            print(f"Validation ok: {validation.ok}")
            print(f"Container records: {container.stats()['records']}")


if __name__ == "__main__":
    main()
