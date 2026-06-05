"""Tests for explicit numeric query tolerance semantics."""

import numpy as np

from usif import (
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
    WyckoffSite,
)
from usif.storage import StructureContainer


def structure_with_energy(formula, energy, coords=(0.0, 0.0, 0.0)):
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, coords)],
        structure_properties=StructureProperties(energy=energy),
        formula=formula,
    )


def test_numeric_property_query_uses_raw_values_and_explicit_tolerance(tmp_path):
    path = tmp_path / "structures.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(structure_with_energy("H", -1.0000), name="exact")
        container.add(structure_with_energy("H", -1.0004, (0.25, 0.0, 0.0)), name="near")

        exact = container.query(properties={"energy": -1.0}, numeric_tolerance=0.0)
        near = container.query(properties={"energy": -1.0}, numeric_tolerance=0.001)

    assert len(exact) == 1
    assert len(near) == 2


def test_energy_range_query_uses_unrounded_boundaries(tmp_path):
    path = tmp_path / "structures.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(structure_with_energy("H", -1.0004, (0.25, 0.0, 0.0)), name="outside")
        container.add(structure_with_energy("H", -1.0), name="inside")

        results = container.query(energy_range=(-1.0001, -0.9999))

    assert len(results) == 1
    assert results[0][1].structure_properties.energy == -1.0
