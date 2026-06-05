"""Large-container indexing and validation behavior."""

from __future__ import annotations

import numpy as np
import pytest

from usif import CompressionType, StorageMode, StructureProperties, StructureType, USIFStructure, WyckoffSite
from usif.storage import StructureContainer


def make_structure(formula: str = "H", energy: float = -1.0, x: float = 0.0) -> USIFStructure:
    props = StructureProperties(energy=energy)
    props.set_vector("dipole", [x, 0.0, 1.0])
    props.set_tensor("elastic", [[1.0 + x, 0.0], [0.0, 2.0]])
    props.set_custom("metadata", {"family": "hydride", "rank": int(abs(energy) * 10)})
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, (x, 0.0, 0.0))],
        structure_properties=props,
        formula=formula,
    )


@pytest.mark.reliability
def test_persisted_secondary_indexes_are_loaded_from_index_payload(tmp_path):
    path = tmp_path / "persisted_indexes.usifc"
    with StructureContainer(path, mode="w", compression=CompressionType.NONE, use_mmap=False) as container:
        container.add(make_structure("H", -1.0, 0.0), name="h1", group="/hydrides")
        container.add(make_structure("H", -2.0, 0.2), name="h2", group="/hydrides")
        container.add(make_structure("He", -0.1, 0.4), name="he")

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        assert container._indexes.secondary_indexes_complete is True
        assert container.list_formulas() == ["H", "He"]
        assert "metadata.family" in container.list_properties()
        assert len(container.query(formula="H")) == 2
        assert len(container.query(properties={"metadata.family": "hydride"})) == 3
        assert len(container.query(properties={"dipole": [0.2, 0.0, 1.0]})) == 1
        assert len(container.query(properties={"elastic": [[1.2, 0.0], [0.0, 2.0]]})) == 1


@pytest.mark.reliability
def test_validation_levels_have_distinct_cost_and_assurance(tmp_path):
    path = tmp_path / "validation_levels.usifc"
    with StructureContainer(path, mode="w", compression=CompressionType.NONE, use_mmap=False) as container:
        record_hash = container.add(make_structure("H", -1.0, 0.0), name="h1")
        chunk_id, chunk_offset, size = container._record_index[record_hash]

    record_offset = chunk_id * StructureContainer.CHUNK_SIZE + chunk_offset
    with open(path, "r+b") as handle:
        handle.seek(record_offset + size - 1)
        last = handle.read(1)
        assert last
        handle.seek(record_offset + size - 1)
        handle.write(bytes([last[0] ^ 0xFF]))

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        index_result = container.validate(level="index")
        records_result = container.validate(level="records")
        full_result = container.validate(level="full")

    assert index_result.ok is True
    assert records_result.ok is True
    assert full_result.ok is False
    assert full_result.level == "full"


@pytest.mark.reliability
def test_rebuild_index_scans_records_without_reading_entire_file(tmp_path, monkeypatch):
    path = tmp_path / "streaming_rebuild.usifc"
    with StructureContainer(path, mode="w", compression=CompressionType.NONE, use_mmap=False) as container:
        container.add(make_structure(), name="first")

    read_sizes = []

    with StructureContainer(path, mode="a", compression=CompressionType.NONE, use_mmap=False) as container:
        assert container._index_offset > container.HEADER_SIZE
        original_read = container._file.read

        def tracked_read(size=-1):
            read_sizes.append(size)
            if size == -1:
                raise AssertionError("rebuild_index must not read the whole container at once")
            return original_read(size)

        monkeypatch.setattr(container._file, "read", tracked_read)
        container._clear_loaded_indexes()
        assert container.rebuild_index() == 1

    assert read_sizes
    assert all(size != -1 for size in read_sizes)
