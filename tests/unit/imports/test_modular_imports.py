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
        from usif.interop.pymatgen import (
            CrystalExporter,
            CrystalImporter,
            MoleculeExporter,
            MoleculeImporter,
            PymatgenExporter,
            PymatgenImporter,
            SymmetryPolicy,
        )
        from usif.storage import StructureContainer, USIFGroup

        self.assertIsNotNone(USIF)
        self.assertIsNotNone(PymatgenImporter)
        self.assertIsNotNone(PymatgenExporter)
        self.assertIsNotNone(CrystalImporter)
        self.assertIsNotNone(MoleculeImporter)
        self.assertIsNotNone(CrystalExporter)
        self.assertIsNotNone(MoleculeExporter)
        self.assertIsNotNone(SymmetryPolicy)
        self.assertIsNotNone(ASEImporter)
        self.assertIsNotNone(ASEExporter)
        self.assertIsNotNone(StructureContainer)
        self.assertIsNotNone(USIFGroup)


    def test_services_imports(self):
        from usif.services import (
            USIFOptimizer,
            export_structure,
            import_pymatgen,
            import_structure,
            load_structure,
            load_structure_json,
            optimize_structure,
            save_structure,
            save_structure_json,
            structure_from_json_dict,
            structure_to_json_dict,
        )

        self.assertIsNotNone(import_structure)
        self.assertIsNotNone(import_pymatgen)
        self.assertIsNotNone(export_structure)
        self.assertIsNotNone(load_structure)
        self.assertIsNotNone(load_structure_json)
        self.assertIsNotNone(save_structure)
        self.assertIsNotNone(save_structure_json)
        self.assertIsNotNone(structure_from_json_dict)
        self.assertIsNotNone(structure_to_json_dict)
        self.assertIsNotNone(USIFOptimizer)
        self.assertIsNotNone(optimize_structure)


    def test_benchmark_imports(self):
        from usif.benchmarks import USIFBenchmark, benchmark_compression

        self.assertIsNotNone(USIFBenchmark)
        self.assertIsNotNone(benchmark_compression)

    def test_materials_project_integration_imports(self):
        from usif.integrations.materials_project import (
            convert_mp_to_usif,
            create_mp_data_archive,
            download_mp_data,
            load_mp_data_from_archive,
            load_mp_group,
            safe_extract,
        )

        self.assertIsNotNone(download_mp_data)
        self.assertIsNotNone(load_mp_group)
        self.assertIsNotNone(convert_mp_to_usif)
        self.assertIsNotNone(create_mp_data_archive)
        self.assertIsNotNone(load_mp_data_from_archive)
        self.assertIsNotNone(safe_extract)

    def test_removed_compatibility_modules(self):
        for module in (
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
        from usif import RELEASE_DATE, RELEASE_ID, RELEASE_RECORD, __author__, __version__

        self.assertEqual(__version__, "6.3.0")
        self.assertEqual(RELEASE_DATE, "2026-06-05")
        self.assertEqual(RELEASE_RECORD, "20260605.006")
        self.assertEqual(RELEASE_ID, "usif-20260605-006")
        self.assertIsNotNone(__author__)


if __name__ == "__main__":
    unittest.main()
