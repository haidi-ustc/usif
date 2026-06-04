"""Regression tests for P0 data correctness fixes."""

import struct

import numpy as np
import pytest

from usif import (
    AtomicProperties,
    AtomSite,
    CompressionType,
    IntegrityError,
    StorageMode,
    StructureContainer,
    StructureConverter,
    StructureProperties,
    StructureType,
    USIF,
    USIFStructure,
    ValidationError,
    WyckoffSite,
)
from usif.format.hashing import calculate_geometry_hash, calculate_record_hash


def make_symmetric_structure(energy=-1.0):
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, (0.0, 0.0, 0.0))],
        structure_properties=StructureProperties(energy=energy),
        formula="H",
    )


def make_full_atomic_structure(force=(0.0, 0.0, 0.0)):
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        atom_sites=[AtomSite(1, (0.0, 0.0, 0.0), AtomicProperties(force=force))],
        formula="H",
    )


def test_decode_rejects_modified_header_hash():
    encoder = USIF(compression=CompressionType.NONE)
    encoded = bytearray(encoder.encode(make_symmetric_structure()))
    encoded[17] ^= 0xFF

    with pytest.raises(IntegrityError):
        encoder.decode(bytes(encoded))


def test_decode_rejects_geometry_payload_mutation():
    encoder = USIF(compression=CompressionType.NONE)
    encoded = bytearray(encoder.encode(make_symmetric_structure()))

    # Raw payload starts at byte 64. For a symmetric crystal, the first Wyckoff
    # coordinate begins after: type(1), mode(1), lattice(36), spacegroup(2),
    # num_sites(1), atomic_number(1), multiplicity(2).
    first_coord_offset = 64 + 1 + 1 + 36 + 2 + 1 + 1 + 2
    encoded[first_coord_offset : first_coord_offset + 4] = struct.pack("<f", 0.5)

    with pytest.raises(IntegrityError):
        encoder.decode(bytes(encoded))


def test_geometry_hash_ignores_properties_but_record_hash_includes_them():
    base = make_symmetric_structure(energy=-1.0)
    changed_energy = make_symmetric_structure(energy=-2.0)

    assert calculate_geometry_hash(base) == calculate_geometry_hash(changed_energy)
    assert calculate_record_hash(base) != calculate_record_hash(changed_energy)

    force_a = make_full_atomic_structure(force=(0.1, 0.0, 0.0))
    force_b = make_full_atomic_structure(force=(0.2, 0.0, 0.0))
    assert calculate_geometry_hash(force_a) == calculate_geometry_hash(force_b)
    assert calculate_record_hash(force_a) != calculate_record_hash(force_b)


def test_container_keeps_same_geometry_with_different_properties(tmp_path):
    path = tmp_path / "records.usifc"
    with StructureContainer(path, mode="w", compression=CompressionType.NONE) as container:
        first_hash = container.add(make_symmetric_structure(energy=-1.0), name="first")
        second_hash = container.add(make_symmetric_structure(energy=-2.0), name="second")

        assert first_hash != second_hash
        assert len(container) == 2
        assert container.get("first").structure_properties.energy == -1.0
        assert container.get("second").structure_properties.energy == -2.0


def test_container_still_deduplicates_identical_records(tmp_path):
    path = tmp_path / "records.usifc"
    structure = make_symmetric_structure(energy=-1.0)
    with StructureContainer(path, mode="w", compression=CompressionType.NONE) as container:
        first_hash = container.add(structure, name="first")
        second_hash = container.add(structure, name="second")

        assert first_hash == second_hash
        assert len(container) == 1


def test_force_symmetric_with_atomic_properties_requires_explicit_policy():
    pytest.importorskip("pymatgen")
    from pymatgen.core import Lattice, Structure

    pmg = Structure(Lattice.cubic(3.0), ["H"], [[0.0, 0.0, 0.0]])
    forces = np.array([[0.1, 0.0, 0.0]])

    with pytest.raises(ValidationError):
        StructureConverter.from_pymatgen(pmg, forces=forces, force_symmetric=True)

    fallback = StructureConverter.from_pymatgen(
        pmg,
        forces=forces,
        force_symmetric=True,
        fallback_full_atomic=True,
    )
    assert fallback.storage_mode == StorageMode.FULL_ATOMIC
    assert fallback.atom_sites[0].properties.force == tuple(forces[0])

    dropped = StructureConverter.from_pymatgen(
        pmg,
        forces=forces,
        force_symmetric=True,
        drop_atomic_properties=True,
    )
    assert dropped.storage_mode == StorageMode.SYMMETRIC
