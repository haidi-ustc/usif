#!/usr/bin/env python3
"""
Test modular imports
Verify that all modules can be imported correctly
"""

import unittest


class TestModularImports(unittest.TestCase):
    """Test that all modules can be imported correctly"""

    def test_core_imports(self):
        """Test core module imports"""
        from usif.constants import (
            BinaryFormat,
            CompressionType,
            StorageMode,
            StructureType,
        )
        from usif.exceptions import DecodingError, EncodingError, USIFError

        self.assertIsNotNone(BinaryFormat)
        self.assertIsNotNone(USIFError)
        self.assertIsNotNone(StructureType)

    def test_properties_imports(self):
        """Test properties module imports"""
        from usif.properties import (
            AtomicProperties,
            PropertyDefinition,
            PropertyRegistry,
            PropertySerializer,
            StructureProperties,
        )

        self.assertIsNotNone(PropertyDefinition)
        self.assertIsNotNone(PropertySerializer)
        self.assertIsNotNone(PropertyRegistry)
        self.assertIsNotNone(AtomicProperties)
        self.assertIsNotNone(StructureProperties)

    def test_structures_imports(self):
        """Test structures module imports"""
        from usif.structures import (
            AtomSite,
            PointGroupSite,
            USIFStructure,
            WyckoffSite,
        )

        self.assertIsNotNone(WyckoffSite)
        self.assertIsNotNone(PointGroupSite)
        self.assertIsNotNone(AtomSite)
        self.assertIsNotNone(USIFStructure)

    def test_core_functionality_imports(self):
        """Test core functionality imports"""
        from usif.container import StructureContainer, USIFGroup
        from usif.converter import StructureConverter
        from usif.encoder import USIF

        self.assertIsNotNone(USIF)
        self.assertIsNotNone(StructureConverter)
        self.assertIsNotNone(StructureContainer)
        self.assertIsNotNone(USIFGroup)

    def test_utils_imports(self):
        """Test utils module imports"""
        from usif.utils import USIFBenchmark, USIFOptimizer

        self.assertIsNotNone(USIFOptimizer)
        self.assertIsNotNone(USIFBenchmark)

    def test_top_level_imports(self):
        """Test top-level package imports (backward compatibility)"""
        from usif import (
            USIF,
            AtomicProperties,
            AtomSite,
            CompressionType,
            PointGroupSite,
            PropertyDefinition,
            PropertyRegistry,
            PropertySerializer,
            StorageMode,
            StructureContainer,
            StructureConverter,
            StructureProperties,
            StructureType,
            USIFBenchmark,
            USIFGroup,
            USIFOptimizer,
            USIFStructure,
            WyckoffSite,
        )

        # Verify all imports are available
        self.assertIsNotNone(USIF)
        self.assertIsNotNone(USIFStructure)
        self.assertIsNotNone(StructureType)
        self.assertIsNotNone(StorageMode)
        self.assertIsNotNone(CompressionType)

    def test_version_info(self):
        """Test version information"""
        from usif import __author__, __version__

        self.assertEqual(__version__, "5.2.0")
        self.assertIsNotNone(__author__)


if __name__ == "__main__":
    unittest.main()
