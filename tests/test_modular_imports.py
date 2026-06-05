#!/usr/bin/env python3
"""Import smoke tests for canonical USIF modules."""

import importlib
import unittest


class TestModularImports(unittest.TestCase):
    """Test that canonical modules can be imported correctly."""

    def test_core_imports(self):
        from usif.constants import BinaryFormat, CompressionType, StorageMode, StructureType
        from usif.exceptions import DecodingError, EncodingError, USIFError

        self.assertIsNotNone(BinaryFormat)
        self.assertIsNotNone(CompressionType)
        self.assertIsNotNone(StorageMode)
        self.assertIsNotNone(StructureType)
        self.assertIsNotNone(USIFError)
        self.assertIsNotNone(EncodingError)
        self.assertIsNotNone(DecodingError)

    def test_properties_imports(self):
        from usif.properties import (
            AtomicProperties,
            DEFAULT_REGISTRY,
            PropertyDefinition,
            PropertySerializer,
            StructureProperties,
            create_default_registry,
        )

        self.assertIsNotNone(PropertyDefinition)
        self.assertIsNotNone(PropertySerializer)
        self.assertIsNotNone(DEFAULT_REGISTRY)
        self.assertIsNotNone(AtomicProperties)
        self.assertIsNotNone(StructureProperties)

    def test_structures_imports(self):
        from usif.structures import AtomSite, PointGroupSite, USIFStructure, WyckoffSite

        self.assertIsNotNone(WyckoffSite)
        self.assertIsNotNone(PointGroupSite)
        self.assertIsNotNone(AtomSite)
        self.assertIsNotNone(USIFStructure)

    def test_canonical_functionality_imports(self):
        from usif.encoder import USIF
        from usif.interop.ase import ASEExporter, ASEImporter
        from usif.interop.pymatgen import PymatgenExporter, PymatgenImporter
        from usif.storage import StructureContainer, USIFGroup

        self.assertIsNotNone(USIF)
        self.assertIsNotNone(PymatgenImporter)
        self.assertIsNotNone(PymatgenExporter)
        self.assertIsNotNone(ASEImporter)
        self.assertIsNotNone(ASEExporter)
        self.assertIsNotNone(StructureContainer)
        self.assertIsNotNone(USIFGroup)


    def test_services_imports(self):
        from usif.services import (
            export_structure,
            import_pymatgen,
            import_structure,
            load_structure,
            save_structure,
        )

        self.assertIsNotNone(import_structure)
        self.assertIsNotNone(import_pymatgen)
        self.assertIsNotNone(export_structure)
        self.assertIsNotNone(load_structure)
        self.assertIsNotNone(save_structure)

    def test_removed_compatibility_modules(self):
        for module in (
            "usif.converter",
            "usif.container",
            "usif.interop.converter_core",
            "usif.interop.symmetry",
            "usif.io",
                "usif.structures.io",
                "usif.structures.source",
        ):
            with self.subTest(module=module):
                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module(module)

    def test_top_level_core_imports(self):
        from usif import (
            USIF,
            AtomicProperties,
            AtomSite,
            CompressionType,
            DEFAULT_REGISTRY,
            PointGroupSite,
            PropertyDefinition,
            PropertySerializer,
            StorageMode,
            StructureProperties,
            StructureType,
            USIFStructure,
            WyckoffSite,
            create_default_registry,
        )

        self.assertIsNotNone(USIF)
        self.assertIsNotNone(USIFStructure)
        self.assertIsNotNone(StructureType)
        self.assertIsNotNone(StorageMode)
        self.assertIsNotNone(CompressionType)
        self.assertIsNotNone(DEFAULT_REGISTRY)
        self.assertIsNotNone(PropertyDefinition)
        self.assertIsNotNone(PropertySerializer)
        self.assertIsNotNone(AtomicProperties)
        self.assertIsNotNone(StructureProperties)
        self.assertIsNotNone(WyckoffSite)
        self.assertIsNotNone(PointGroupSite)
        self.assertIsNotNone(AtomSite)

    def test_version_info(self):
        from usif import __author__, __version__

        self.assertEqual(__version__, "5.6.0")
        self.assertIsNotNone(__author__)


if __name__ == "__main__":
    unittest.main()
