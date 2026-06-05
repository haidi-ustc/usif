"""Runtime-code guardrails for the 7.1 cleanup line."""

from __future__ import annotations

from pathlib import Path


def test_property_codec_has_single_canonical_module():
    assert not Path("usif/format/properties.py").exists()
    source = Path("usif/format/binary/property_codec.py").read_text(encoding="utf-8")
    assert "usif.format.properties" not in source
    assert "historical" not in source.lower()


def test_runtime_code_has_no_migration_stage_terms():
    forbidden = (
        "historical implementation",
        "backward-compatible",
        "compatibility facade",
        "Transitional",
        "P1 ",
        "P2 ",
        "P3 ",
        "old fallback",
        "older payload",
        "alias for add",
    )
    for path in Path("usif").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in text, f"{path} contains {term!r}"


def test_container_api_exposes_single_add_and_validation_form():
    from inspect import signature

    from usif.storage import StructureContainer

    assert hasattr(StructureContainer, "add")
    assert not hasattr(StructureContainer, "add_structure")
    assert "decode_records" not in signature(StructureContainer.validate).parameters
