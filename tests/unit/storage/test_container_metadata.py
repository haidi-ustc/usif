"""Container metadata and batch-read regression tests."""

import numpy as np
import pytest

from usif import (
    CompressionType,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
    WyckoffSite,
)
from usif.storage import StructureContainer


def make_structure(energy=-1.0):
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, (0.0, 0.0, 0.0))],
        structure_properties=StructureProperties(energy=energy),
        formula="H",
    )


def test_duplicate_record_adds_new_alias_group_and_attributes(tmp_path):
    path = tmp_path / "duplicate_metadata.usifc"
    structure = make_structure()

    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        first_hash = container.add(structure, name="first", group="/a")
        second_hash = container.add(
            structure,
            name="second",
            group="/b",
            attributes={"temperature": 300, "metadata": {"source": "copy"}},
        )

        assert first_hash == second_hash
        assert len(container) == 1
        assert container.get("first") is not None
        assert container.get("second") is not None
        assert "first" in container.get_group("/a").structures
        assert "second" in container.get_group("/b").structures
        assert container.get_structure_attributes("second") == {
            "temperature": 300,
            "metadata": {"source": "copy"},
        }

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        assert len(container) == 1
        assert container.get("first") is not None
        assert container.get("second") is not None
        assert "second" in container.get_group("/b").structures
        assert container.get_structure_attributes("second") == {
            "temperature": 300,
            "metadata": {"source": "copy"},
        }


def test_container_attributes_preserve_json_types(tmp_path):
    path = tmp_path / "typed_attrs.usifc"
    attrs = {
        "integer": 1,
        "float": 1.5,
        "bool": True,
        "none": None,
        "list": [1, "two", False],
        "dict": {"nested": [1, 2, 3]},
        "string_number": "001",
    }

    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        container.add(make_structure(), name="typed", attributes=attrs)
        container.set_group_attribute("/typed_group", "attrs", attrs)

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        assert container.get_structure_attributes("typed") == attrs
        assert container.get_group_attribute("/typed_group", "attrs") == attrs


def test_set_structure_attributes_rejects_read_only_container(tmp_path):
    path = tmp_path / "readonly_attrs.usifc"
    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        container.add(make_structure(), name="readonly")

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        with pytest.raises(ValueError, match="read-only"):
            container.set_structure_attributes("readonly", {"x": 1})


def test_parallel_batch_read_preserves_duplicate_identifier_positions(tmp_path):
    path = tmp_path / "batch_duplicates.usifc"
    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        container.add(make_structure(energy=-1.0), name="first")
        container.add(make_structure(energy=-2.0), name="second")

        results = container.get_batch_parallel(["first", "second", "first", "missing"])

    assert results[0] is not None
    assert results[1] is not None
    assert results[2] is not None
    assert results[3] is None
    assert results[0].structure_properties.energy == results[2].structure_properties.energy
    assert results[1].structure_properties.energy == -2.0
