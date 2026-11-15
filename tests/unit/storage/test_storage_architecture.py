"""Storage and architectural boundary smoke tests."""

import importlib
import inspect
from pathlib import Path


REMOVED_COMPATIBILITY_MODULES = (
    "usif.converter",
    "usif.container",
    "usif.interop.converter_core",
    "usif.interop.symmetry",
    "usif.io",
    "usif.structures.io",
    "usif.structures.source",
    "usif.utils",
    "usif.utils.optimizer",
    "usif.utils.benchmark",
    "usif.utils.mp_downloader",
    "usif.format.properties",
    "usif.symmetry.metadata",
)


def test_encoder_is_thin_facade_and_binary_modules_are_importable():
    from usif.encoder import USIF
    from usif.format.binary import StructureBinaryCodec, USIFHeader, validate_geometry_hash

    assert USIF is not None
    assert USIFHeader is not None
    assert StructureBinaryCodec is not None
    assert validate_geometry_hash is not None
    assert "structure_codec.encode_body" in inspect.getsource(USIF._encode_body)
    assert "structure_codec.decode_body" in inspect.getsource(USIF._decode_body)


def test_removed_adapter_facades_are_gone():
    for module in REMOVED_COMPATIBILITY_MODULES:
        try:
            importlib.import_module(module)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"removed facade module still importable: {module}")


def test_canonical_interop_adapters_share_the_array_layer():
    from usif.interop.ase import ASEExporter, ASEImporter
    from usif.interop.matsimpy import MatsimpyExporter, MatsimpyImporter
    from usif.interop.pymatgen import PymatgenExporter, PymatgenImporter

    for importer in (
        PymatgenImporter.from_pymatgen,
        ASEImporter.from_ase,
        MatsimpyImporter.from_matsimpy,
    ):
        assert "import_atoms(" in inspect.getsource(importer)
    for exporter in (
        PymatgenExporter.to_pymatgen,
        ASEExporter.to_ase,
        MatsimpyExporter.to_matsimpy,
    ):
        assert "structure_to_arrays(" in inspect.getsource(exporter)
    ase_source = Path("usif/interop/ase/adapter.py").read_text()
    assert "import pymatgen" not in ase_source
    assert "from pymatgen" not in ase_source
    assert "usif.interop.pymatgen" not in ase_source


def test_core_imports_no_optional_structure_library():
    import subprocess
    import sys

    code = (
        "import sys, usif, usif.services, usif.storage, usif.interop, usif.symmetry, usif.cli;"
        "import usif.integrations.materials_project, usif.benchmarks;"
        "loaded = [m for m in ('pymatgen', 'ase', 'matsimpy') if m in sys.modules];"
        "print(','.join(loaded))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""


def test_symmetry_package_uses_lazy_reducer_import_and_explicit_policy():
    import usif.symmetry as symmetry
    from usif.symmetry import SymmetryPolicy, apply_symmetry_policy

    init_source = Path("usif/symmetry/__init__.py").read_text()
    top_level_imports = [line for line in init_source.splitlines() if line.startswith("from ")]
    assert all("symmetry.reduce" not in line for line in top_level_imports)
    assert SymmetryPolicy is not None
    assert callable(apply_symmetry_policy)
    assert symmetry.SymmetryReducer is not None
    assert callable(symmetry.expand_structure)


def test_structure_model_has_no_io_or_conversion_methods():
    from usif.structures.structure import USIFStructure

    for method_name in ("from_source", "from_pymatgen", "to", "save", "load"):
        assert not hasattr(USIFStructure, method_name)

    source = inspect.getsource(USIFStructure)
    assert "usif.services" not in source
    assert "usif.interop" not in source
    assert "usif.encoder" not in source


def test_services_are_canonical_application_boundary():
    from usif.services import (
        export_structure,
        import_pymatgen,
        import_structure,
        load_structure,
        save_structure,
    )

    assert import_structure is not None
    assert import_pymatgen is not None
    assert export_structure is not None
    assert save_structure is not None
    assert load_structure is not None


def test_services_benchmarks_and_integrations_have_explicit_boundaries():
    from usif.benchmarks import USIFBenchmark, benchmark_compression
    from usif.integrations.materials_project import (
        convert_mp_to_usif,
        create_mp_data_archive,
        download_mp_data,
        load_mp_data_from_archive,
        load_mp_group,
        safe_extract,
    )
    from usif.services import USIFOptimizer, optimize_structure

    assert USIFOptimizer is not None
    assert optimize_structure is not None
    assert USIFBenchmark is not None
    assert benchmark_compression is not None
    assert download_mp_data is not None
    assert load_mp_group is not None
    assert convert_mp_to_usif is not None
    assert create_mp_data_archive is not None
    assert load_mp_data_from_archive is not None
    assert safe_extract is not None

    assert not Path("usif/utils").exists()
    assert Path("usif/services/optimizer.py").exists()
    assert Path("usif/benchmarks/compression.py").exists()
    assert Path("usif/integrations/materials_project/downloader.py").exists()


def test_materials_project_integration_is_split_into_focused_modules():
    mp_root = Path("usif/integrations/materials_project")
    expected = {
        "archive.py",
        "client.py",
        "dependencies.py",
        "downloader.py",
        "loader.py",
        "mapper.py",
        "query.py",
    }
    assert expected.issubset({path.name for path in mp_root.glob("*.py")})
    downloader_source = (mp_root / "downloader.py").read_text()
    assert "MaterialsProjectClient" in downloader_source
    assert "create_mp_data_archive" in downloader_source
    assert "convert_mp_to_usif" not in downloader_source
    assert "safe_extract" not in downloader_source


def test_registry_default_factory_creates_isolated_registry():
    from usif import DEFAULT_REGISTRY, PropertyDefinition, create_default_registry

    registry = create_default_registry()
    registry.register(PropertyDefinition("storage_arch_isolated_prop", float))
    assert registry.exists("storage_arch_isolated_prop")
    assert not DEFAULT_REGISTRY.exists("storage_arch_isolated_prop")


def test_storage_container_uses_composed_record_and_index_stores():
    """StructureContainer delegates low-level storage to composed stores."""
    from usif.storage.container import StructureContainer
    from usif.storage.index_store import ContainerIndexStore
    from usif.storage.record_store import RecordStore

    container_lines = Path("usif/storage/container.py").read_text().count("\n") + 1
    assert container_lines < 600
    source = inspect.getsource(StructureContainer.__init__)
    assert "RecordStore(" in source
    assert "ContainerIndexStore(" in source
    assert RecordStore is not None
    assert ContainerIndexStore is not None


def test_container_index_reader_does_not_materialize_entire_file():
    """Index loading reads bounded blocks through ContainerIndexStore."""
    source = Path("usif/storage/index_persistence.py").read_text()
    assert "bytes(self._mmap[:])" not in source
    assert "self._file.read()" not in source
    assert "read_index_block_at" in source
    assert "find_latest_valid_index_offset" in source


def test_removed_obsolete_container_code_paths():
    """No unchecked obsolete index/attribute fallback remains in storage modules."""
    storage_text = "\n".join(
        path.read_text()
        for path in Path("usif/storage").glob("*.py")
        if path.name != "__init__.py"
    )
    assert "str(value)" not in storage_text
    assert "_read_group_hierarchy" not in storage_text
    assert "_deserialize_indexes(" not in storage_text
    assert "strict=False" not in storage_text


def test_record_store_owns_chunk_access_without_file_store_facade():
    from usif.storage.record_store import ChunkedRecordAccess, RecordStore

    assert RecordStore is not None
    assert ChunkedRecordAccess is not None
    assert not Path("usif/storage/file_store.py").exists()
    record_store_source = Path("usif/storage/record_store.py").read_text()
    assert "class ChunkedRecordAccess" in record_store_source
    assert "ChunkedFileStore" not in record_store_source


def test_container_exposes_validation_service():
    from usif.storage import ContainerValidationResult, StructureContainer
    from usif.storage.validation import ContainerValidator

    assert StructureContainer.validate is not None
    assert ContainerValidator is not None
    assert ContainerValidationResult is not None
    source = Path("usif/storage/container.py").read_text()
    assert "ContainerValidator(self).validate(level=level)" in source
    validation_source = Path("usif/storage/validation.py").read_text()
    assert 'level: ValidationLevel = "index"' in validation_source
    assert "record byte range" in validation_source
    assert "hash mismatch after decode" in validation_source


def test_container_persists_secondary_indexes_for_large_reads():
    source = Path("usif/storage/index_persistence.py").read_text()
    assert "SECONDARY_INDEX_MAGIC" in source
    assert "_serialize_secondary_indexes" in source
    assert "_deserialize_secondary_indexes" in source
    assert "_ensure_secondary_indexes_loaded" not in source
    assert "Missing secondary index section" in source
    assert "SIDX0002" in source


def test_rebuild_index_uses_streaming_record_scan():
    source = Path("usif/storage/recovery.py").read_text()
    assert "whole container file" in source
    assert "self._file.read()" not in source
    assert "self._file.read(record_size)" in source


def test_storage_public_api_hides_internal_mixins():
    import usif.storage as storage

    assert set(storage.__all__) == {
        "ContainerValidationResult",
        "StructureContainer",
        "USIFGroup",
    }
    for internal_name in (
        "AttributeCodecMixin",
        "GroupOperationsMixin",
        "IndexPersistenceMixin",
        "StorageIOMixin",
        "PrefetchMixin",
        "RecoveryMixin",
        "RecordStore",
        "ContainerIndexStore",
        "QueryEngine",
    ):
        assert not hasattr(storage, internal_name)


def test_binary_property_codec_has_single_canonical_module():
    assert not Path("usif/format/properties.py").exists()
    source = Path("usif/format/binary/property_codec.py").read_text()
    assert "usif.format.properties" not in source
    assert "historical" not in source.lower()
    assert "class PropertyCodec" in source


def test_runtime_code_has_no_migration_phase_terms():
    forbidden = (
        "historical",
        "legacy",
        "backward-compatible",
        "compatibility facade",
        "transitional",
        "old fallback",
        "older payload",
        "P1 ",
        "P2 ",
        "P3 ",
        "alias for add",
    )
    for path in Path("usif").rglob("*.py"):
        text = path.read_text().lower()
        for term in forbidden:
            assert term.lower() not in text, f"{path} contains {term!r}"


def test_container_public_api_has_no_transition_helpers():
    from usif.storage.container import StructureContainer

    assert not hasattr(StructureContainer, "add_structure")
    source = Path("usif/storage/container.py").read_text()
    assert "decode_records" not in source
    assert "total_structures" not in source


def test_symmetry_metadata_is_not_a_forwarding_module():
    assert not Path("usif/symmetry/metadata.py").exists()
