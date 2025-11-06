#!/usr/bin/env python3
"""
Tests for USIF StructureContainer
Test container functionality for storing multiple structures
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from usif import StructureContainer, USIFStructure, StructureType, StorageMode
from usif import WyckoffSite, StructureProperties, CompressionType
import numpy as np


class TestStructureContainer(unittest.TestCase):
    """Test StructureContainer class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.usifc')
        self.temp_path = self.temp_file.name
        self.temp_file.close()
        
        self.structure = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(14, 8, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=-10.5),
            formula="Si"
        )
    
    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_path):
            os.unlink(self.temp_path)
    
    def test_create_container_write_mode(self):
        """Test creating container in write mode"""
        container = StructureContainer(self.temp_path, mode='w')
        self.assertEqual(container.mode, 'w')
        container.close()
    
    def test_create_container_read_mode(self):
        """Test creating container in read mode (should fail if file doesn't exist)"""
        # First create a container and close it
        container = StructureContainer(self.temp_path, mode='w')
        container.close()
        
        # Now open in read mode
        container = StructureContainer(self.temp_path, mode='r')
        self.assertEqual(container.mode, 'r')
        container.close()
    
    def test_add_structure(self):
        """Test adding structure to container"""
        container = StructureContainer(self.temp_path, mode='w')
        struct_hash = container.add(self.structure, name="test_structure")
        self.assertIsNotNone(struct_hash)
        self.assertIsInstance(struct_hash, str)
        container.close()
    
    def test_get_structure_same_session(self):
        """Test getting structure from container in same session"""
        with StructureContainer(self.temp_path, mode='w') as container:
            struct_hash = container.add(self.structure, name="test_structure")
            retrieved = container.get(struct_hash)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.formula, self.structure.formula)
    
    def test_get_structure_by_name_same_session(self):
        """Test getting structure by name in same session"""
        with StructureContainer(self.temp_path, mode='w') as container:
            struct_hash = container.add(self.structure, name="test_structure")
            retrieved = container.get("test_structure")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.formula, self.structure.formula)
    
    def test_list_structures_same_session(self):
        """Test listing structures in container in same session"""
        with StructureContainer(self.temp_path, mode='w') as container:
            container.add(self.structure, name="test_structure")
            structures = list(container)
            self.assertGreater(len(structures), 0)
    
    def test_container_with_compression_same_session(self):
        """Test container with different compression types in same session"""
        for comp_type in [CompressionType.NONE, CompressionType.GZIP]:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.usifc')
            temp_path = temp_file.name
            temp_file.close()
            
            try:
                with StructureContainer(temp_path, mode='w', compression=comp_type) as container:
                    struct_hash = container.add(self.structure)
                    retrieved = container.get(struct_hash)
                    self.assertIsNotNone(retrieved)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
    
    def test_container_stats(self):
        """Test container statistics"""
        with StructureContainer(self.temp_path, mode='w') as container:
            container.add(self.structure, name="test_structure")
            stats = container.stats()
            self.assertIsInstance(stats, dict)
            self.assertIn('total_structures', stats)
            self.assertGreater(stats['total_structures'], 0)
    
    def test_container_len(self):
        """Test container length"""
        with StructureContainer(self.temp_path, mode='w') as container:
            container.add(self.structure, name="test_structure")
            self.assertGreater(len(container), 0)
    
    def test_container_contains(self):
        """Test container contains check"""
        with StructureContainer(self.temp_path, mode='w') as container:
            struct_hash = container.add(self.structure, name="test_structure")
            self.assertIn(struct_hash, container)
            self.assertIn("test_structure", container)


if __name__ == '__main__':
    unittest.main()

