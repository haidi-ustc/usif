"""Structures built by the interop array layer keep their record hash after decode."""

from __future__ import annotations

import numpy as np

from usif import USIF, CompressionType, USIFStructure
from usif.interop.common import build_structure
from usif.storage import StructureContainer


def _structure_with_import_props() -> USIFStructure:
    return build_structure(
        [1],
        [[0.0, 0.0, 0.0]],
        lattice=np.eye(3) * 2.5,
        cartesian=False,
        atomic={
            "force": [[0.1, 0.0, 0.0]],
            "charge": [-0.25],
            "magmom": [1.0],
        },
        energy=-1.0,
        stress=np.eye(3),
        custom={"calculator": "example"},
    )


def test_import_property_helpers_set_default_units_before_hashing():
    structure = _structure_with_import_props()
    assert structure.structure_properties.get_units("energy") == "eV"
    assert structure.structure_properties.get_units("stress") == "GPa"
    assert structure.structure_properties.get_units("volume") == "Å^3"
    assert structure.atom_sites[0].properties.get_units("force") == "eV/Å"
    assert structure.atom_sites[0].properties.get_units("charge") == "e"
    assert structure.atom_sites[0].properties.get_units("magmom") == "μB"

    codec = USIF(compression=CompressionType.NONE)
    original_hash = codec.get_record_hash(structure)
    decoded, _ = codec.decode(codec.encode(structure))
    assert codec.get_record_hash(decoded) == original_hash


def test_full_container_validation_accepts_imported_properties(tmp_path):
    path = tmp_path / "imported.usifc"
    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        container.add(_structure_with_import_props(), name="imported")

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        result = container.validate(level="full")

    assert result.ok, result.errors
    assert result.checked_records == 1
    assert result.elapsed_seconds >= 0.0
