#!/usr/bin/env python3
"""
Test modular imports
Verify that all modules can be imported correctly
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestModularImports(unittest.TestCase):
    """Test that all modules can be imported correctly"""
    
    def test_core_imports(self):
        """Test core module imports"""
        from usif.constants import BinaryFormat
        from usif.exceptions import USIFError, EncodingError, DecodingError
        from usif.enums import StructureType, StorageMode, CompressionType
        
        self.assertIsNotNone(BinaryFormat)
        self.assertIsNotNone(USIFError)
        self.assertIsNotNone(StructureType)
    
    def test_properties_imports(self):
        """Test properties module imports"""
        from usif.properties import (
            PropertyDefinition,
            PropertySerializer,
            PropertyRegistry,
            AtomicProperties,
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
            WyckoffSite,
            PointGroupSite,
            AtomSite,
            USIFStructure,
        )
        
        self.assertIsNotNone(WyckoffSite)
        self.assertIsNotNone(PointGroupSite)
        self.assertIsNotNone(AtomSite)
        self.assertIsNotNone(USIFStructure)
    
    def test_core_functionality_imports(self):
        """Test core functionality imports"""
        from usif.encoder import USIF
        from usif.converter import StructureConverter
        from usif.container import StructureContainer, USIFGroup
        
        self.assertIsNotNone(USIF)
        self.assertIsNotNone(StructureConverter)
        self.assertIsNotNone(StructureContainer)
        self.assertIsNotNone(USIFGroup)
    
    def test_utils_imports(self):
        """Test utils module imports"""
        from usif.utils import USIFOptimizer, USIFBenchmark
        
        self.assertIsNotNone(USIFOptimizer)
        self.assertIsNotNone(USIFBenchmark)
    
    def test_top_level_imports(self):
        """Test top-level package imports (backward compatibility)"""
        from usif import (
            USIF,
            USIFStructure,
            StructureType,
            StorageMode,
            CompressionType,
            PropertyDefinition,
            PropertySerializer,
            PropertyRegistry,
            AtomicProperties,
            StructureProperties,
            WyckoffSite,
            PointGroupSite,
            AtomSite,
            StructureConverter,
            StructureContainer,
            USIFGroup,
            USIFOptimizer,
            USIFBenchmark,
        )
        
        # Verify all imports are available
        self.assertIsNotNone(USIF)
        self.assertIsNotNone(USIFStructure)
        self.assertIsNotNone(StructureType)
        self.assertIsNotNone(StorageMode)
        self.assertIsNotNone(CompressionType)
    
    def test_version_info(self):
        """Test version information"""
        from usif import __version__, __author__
        
        self.assertEqual(__version__, "4.0")
        self.assertIsNotNone(__author__)


if __name__ == '__main__':
    unittest.main()

