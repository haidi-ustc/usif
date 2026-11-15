"""Regression tests for data-loss and integrity bugs fixed in 0.8.0."""

from __future__ import annotations

import numpy as np
import pytest

from usif import (
    USIF,
    AtomicProperties,
    AtomSite,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
)
from usif.exceptions import ContainerError, EncodingError, ValidationError
from usif.services import load_structure, save_structure
from usif.storage import StructureContainer


def _crystal(energy: float = -1.0, shift: float = 0.0) -> USIFStructure:
    # Coordinates that are not exactly representable in float32, so the stored
    # form differs from the in-memory form in the last bits.
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3) * 4.1,
        atom_sites=[
            AtomSite(11, (0.1 + shift, 0.2, 0.3), AtomicProperties(charge=0.1)),
            AtomSite(17, (0.6, 0.7, 0.8 + shift), AtomicProperties(charge=-0.1)),
        ],
        structure_properties=StructureProperties(energy=energy),
        formula="NaCl",
    )


def test_failed_save_keeps_existing_file(tmp_path):
    path = tmp_path / "s.usif"
    save_structure(_crystal(), path)
    original = path.read_bytes()

    bad = _crystal()
    bad.structure_properties.custom["value"] = complex(1, 2)
    with pytest.raises(EncodingError):
        save_structure(bad, path)

    assert path.read_bytes() == original
    assert [p.name for p in tmp_path.iterdir()] == ["s.usif"]  # no temp left over


def test_failed_json_save_keeps_existing_file(tmp_path):
    path = tmp_path / "s.usif.json"
    save_structure(_crystal(), path)
    original = path.read_text()
    bad = _crystal()
    bad.structure_properties.custom["value"] = object()
    with pytest.raises(Exception):
        save_structure(bad, path)
    assert path.read_text() == original


def test_non_json_custom_values_are_rejected_not_stringified():
    structure = _crystal()
    structure.structure_properties.custom["value"] = complex(1, 2)
    with pytest.raises(EncodingError):
        USIF().encode(structure)


def test_record_hash_is_stable_across_save_and_load(tmp_path):
    codec = USIF()
    structure = _crystal()
    structure.structure_properties.custom["pair"] = (1, 2)  # tuple reads back as list
    path = tmp_path / "s.usif"
    save_structure(structure, path)
    loaded = load_structure(path)
    assert codec.get_record_hash(structure) == codec.get_record_hash(loaded)

    container_path = tmp_path / "c.usifc"
    with StructureContainer(container_path, mode="w") as container:
        first = container.add(structure, name="a")
        assert container.add(loaded, name="b") == first  # deduplicated
        assert len(container) == 1
    with StructureContainer(container_path, mode="r") as container:
        result = container.validate(level="full")
        assert result.ok, result.errors


def test_mode_w_does_not_truncate_until_close(tmp_path):
    path = tmp_path / "c.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(_crystal(), name="old")

    writer = StructureContainer(path, mode="w")
    writer.add(_crystal(energy=-2.0), name="new")
    with StructureContainer(path, mode="r") as reader:  # old data still intact
        assert reader.list_names() == ["old"]
    writer.close()
    with StructureContainer(path, mode="r") as reader:
        assert reader.list_names() == ["new"]


def test_second_writer_is_rejected(tmp_path):
    path = tmp_path / "c.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(_crystal(), name="base")
    with StructureContainer(path, mode="a") as writer:
        with pytest.raises(ContainerError):
            StructureContainer(path, mode="a")
        with pytest.raises(ContainerError):
            StructureContainer(path, mode="w")
        writer.add(_crystal(energy=-3.0), name="later")
    with StructureContainer(path, mode="r") as reader:
        assert reader.list_names() == ["base", "later"]


def test_invalid_metadata_is_rejected_at_call_time(tmp_path):
    path = tmp_path / "c.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(_crystal(), name="ok")
        with pytest.raises(ValidationError):
            container.add(_crystal(energy=-5.0), name="x" * 70000)
        with pytest.raises(ValidationError):
            container.set_group_attribute("/g", "k", {1, 2})
        with pytest.raises(ValidationError):
            container.add(_crystal(energy=-6.0), attributes={"k": {1, 2}})
    with StructureContainer(path, mode="r") as reader:  # close still succeeded
        assert reader.list_names() == ["ok"]
        assert len(reader) == 1


def test_crashed_writer_records_are_detected_and_recoverable(tmp_path):
    path = tmp_path / "c.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(_crystal(), name="committed")

    writer = StructureContainer(path, mode="a")
    writer.add(_crystal(energy=-2.0))
    writer.add(_crystal(energy=-3.0))
    # Simulate a crash: release the handles without committing an index.
    writer._record_store.close()
    writer._file = None

    with StructureContainer(path, mode="a") as reopened:
        assert len(reopened) == 1
        assert reopened.uncommitted_bytes > 0
        assert reopened.rebuild_index(persist=True) == 3

    with StructureContainer(path, mode="r") as reader:
        assert len(reader) == 3


def test_flush_commits_index(tmp_path):
    path = tmp_path / "c.usifc"
    writer = StructureContainer(path, mode="w", autocommit_every=None)
    writer.add(_crystal(), name="a")
    writer.flush()
    writer.close()
    with StructureContainer(path, mode="r") as reader:
        assert reader.list_names() == ["a"]
        assert reader.uncommitted_bytes == 0


def test_autocommit_every(tmp_path):
    path = tmp_path / "c.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(_crystal())
    writer = StructureContainer(path, mode="a", autocommit_every=2)
    writer.add(_crystal(energy=-2.0), name="b")
    writer.add(_crystal(energy=-3.0), name="c")  # triggers a commit
    writer._record_store.close()
    writer._file = None
    with StructureContainer(path, mode="r") as reader:
        assert reader.list_names() == ["b", "c"]


def test_cache_follows_rebound_names_and_returns_copies(tmp_path):
    path = tmp_path / "c.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(_crystal(energy=-1.0), name="a", attributes={"step": 1})
        assert container.get("a").structure_properties.energy == -1.0

        container.add(_crystal(energy=-2.0), name="a")
        assert container.get("a").structure_properties.energy == -2.0
        # Attributes described the old record and are dropped on rebind.
        assert container.get_structure_attributes("a") is None

        fetched = container.get("a")
        fetched.formula = "MUTATED"
        assert container.get("a").formula == "NaCl"
