"""Interop import property setters preserve record hashes after decode."""

from __future__ import annotations

import numpy as np

from usif import CompressionType, StorageMode, StructureProperties, StructureType, USIF, USIFStructure, WyckoffSite
from usif.interop.pymatgen.property_extractor import build_structure_properties, crystal_atomic_sites
from usif.storage import StructureContainer


class _Specie:
    Z = 1


class _Site:
    specie = _Specie()

    def __init__(self, coords):
        self.coords = tuple(coords)
        self.frac_coords = tuple(coords)


def _structure_with_import_props() -> USIFStructure:
    props = build_structure_properties(
        energy=-1.0,
        stress=np.eye(3),
        volume=12.5,
        custom={"calculator": "example"},
    )
    sites = crystal_atomic_sites(
        [_Site((0.0, 0.0, 0.0))],
        forces=np.array([[0.1, 0.0, 0.0]]),
        charges=np.array([-0.25]),
        magmoms=np.array([1.0]),
    )
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        atom_sites=sites,
        structure_properties=props,
        formula="H",
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
    with StructureContainer(path, mode="w", compression=CompressionType.NONE, use_mmap=False) as container:
        container.add(_structure_with_import_props(), name="imported")

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        result = container.validate(level="full")

    assert result.ok, result.errors
    assert result.checked_records == 1
    assert result.elapsed_seconds >= 0.0
