"""P2 architecture boundary smoke tests."""

import inspect


def test_encoder_is_thin_facade_and_binary_modules_are_importable():
    from usif.encoder import USIF
    from usif.format.binary import StructureBinaryCodec, USIFHeader, validate_geometry_hash

    assert USIF is not None
    assert USIFHeader is not None
    assert StructureBinaryCodec is not None
    assert validate_geometry_hash is not None
    assert "structure_codec.encode_body" in inspect.getsource(USIF.encode)
    assert "structure_codec.decode_body" in inspect.getsource(USIF.decode)


def test_container_top_level_reexports_storage_implementation():
    from usif.container import StructureContainer as PublicContainer
    from usif.storage.container import StructureContainer as StorageContainer

    assert PublicContainer is StorageContainer


def test_converter_facade_routes_to_interop_packages():
    from usif.converter import StructureConverter
    from usif.interop.ase import ASEExporter, ASEImporter
    from usif.interop.pymatgen import PymatgenExporter, PymatgenImporter

    assert StructureConverter is not None
    assert ASEImporter is not None
    assert ASEExporter is not None
    assert PymatgenImporter is not None
    assert PymatgenExporter is not None
    assert "usif.interop.pymatgen.importer" in inspect.getsource(
        StructureConverter.from_pymatgen
    )
    assert "usif.interop.ase.importer" in inspect.getsource(
        StructureConverter.from_ase
    )


def test_symmetry_package_is_single_source_import_path():
    from usif.interop.symmetry import SymmetryOperations as CompatOperations
    from usif.symmetry import SymmetryOperations as PackageOperations
    from usif.symmetry import SymmetryReducer

    assert CompatOperations is PackageOperations
    assert SymmetryReducer is not None


def test_io_facade_is_public_and_structure_methods_delegate():
    from usif.io import convert_to, from_pymatgen, from_source, load_structure, save_structure
    from usif.structures.structure import USIFStructure

    assert from_source is not None
    assert from_pymatgen is not None
    assert convert_to is not None
    assert save_structure is not None
    assert load_structure is not None
    assert "usif.io.facade" in inspect.getsource(USIFStructure.from_source)
    assert "usif.io.facade" in inspect.getsource(USIFStructure.save)


def test_registry_default_factory_and_isolated_registry():
    from usif import PropertyDefinition, PropertyRegistry, default_registry, isolated_registry

    assert default_registry() is PropertyRegistry
    registry = isolated_registry()
    registry.register(PropertyDefinition("p2_isolated_prop", float))
    assert registry.exists("p2_isolated_prop")
    assert not PropertyRegistry.exists("p2_isolated_prop")
