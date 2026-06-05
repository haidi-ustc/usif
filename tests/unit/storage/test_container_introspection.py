"""Container introspection and enhanced query tests."""

from __future__ import annotations

import numpy as np

from usif import StorageMode, StructureProperties, StructureType, USIFStructure, WyckoffSite
from usif.storage import StructureContainer


def make_structure(formula: str, energy: float, family: str, x: float = 0.0) -> USIFStructure:
    props = StructureProperties(energy=energy)
    props.set_vector("dipole", [x, 0.0, 1.0], units="Debye")
    props.set_custom("metadata", {"family": family, "rank": int(abs(energy) * 10)})
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, (x, 0.0, 0.0))],
        structure_properties=props,
        formula=formula,
    )


def test_container_lists_and_stats_do_not_decode_records(tmp_path, monkeypatch):
    path = tmp_path / "introspection.usifc"
    with StructureContainer(path, mode="w", use_mmap=False) as container:
        container.add(make_structure("H", -1.0, "hydride"), name="h1", group="/materials/hydrides")
        container.add(make_structure("He", -0.1, "noble", 0.2), name="he1", group="/materials/noble")

    def fail_get(identifier):  # pragma: no cover - executed only on regression
        raise AssertionError("introspection must use persisted indexes, not decode records")

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        monkeypatch.setattr(container, "get", fail_get)
        assert container.list_names() == ["h1", "he1"]
        assert container.list_formulas() == ["H", "He"]
        assert "energy" in container.list_properties()
        assert "metadata.family" in container.list_properties()
        assert "/materials/hydrides/" in container.list_groups()
        stats = container.stats()

    assert stats["records"] == 2
    assert stats["unique_formulas"] == 2
    assert "energy" in stats["properties"]
    assert stats["file_size_bytes"] > 0
    assert stats["index_size_bytes"] > 0
    assert stats["record_bytes"] > 0
    assert stats["cache"]["entries"] == 0
    assert stats["storage"]["chunk_size_bytes"] > 0
    assert stats["record_bytes"] > 0
    assert stats["cache"]["entries"] >= 0
    assert stats["storage"]["chunk_size_bytes"] > 0


def test_enhanced_query_filters(tmp_path):
    path = tmp_path / "query_filters.usifc"
    with StructureContainer(path, mode="w", use_mmap=False) as container:
        container.add(make_structure("H", -1.0, "hydride"), name="h1", group="/materials/hydrides")
        container.add(make_structure("H", -2.0, "hydride", 0.2), name="h2", group="/materials/hydrides")
        container.add(make_structure("He", -0.1, "noble", 0.4), name="he1", group="/materials/noble")

    with StructureContainer(path, mode="r", use_mmap=False) as container:
        assert len(container.query(has_property="dipole")) == 3
        assert len(container.query(property_range=("energy", -2.1, -1.5))) == 1
        assert len(container.query(custom={"metadata.family": "hydride"})) == 2
        assert len(container.query(formula="H", custom={"metadata.rank": 10})) == 1
