#!/usr/bin/env python3
"""
Test modular structure functionality
Verify that modular structure works correctly
"""

import unittest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from usif import (
    USIFStructure, StructureType, StorageMode,
    WyckoffSite, AtomSite, AtomicProperties, StructureProperties,
    USIF, CompressionType
)


class TestModularStructure(unittest.TestCase):
    """Test structure creation and operations with modular imports"""
    
    def test_create_periodic_structure(self):
        """Test creating a periodic structure"""
        lattice = np.array([
            [5.0, 0.0, 0.0],
            [0.0, 5.0, 0.0],
            [0.0, 0.0, 5.0]
        ])
        
        wyckoff_sites = [
            WyckoffSite(atomic_number=14, multiplicity=8, coords=(0.0, 0.0, 0.0))
        ]
        
        structure = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice,
            spacegroup=227,
            wyckoff_sites=wyckoff_sites,
            structure_properties=StructureProperties(energy=-10.5),
            formula="Si"
        )
        
        self.assertEqual(structure.formula, "Si")
        self.assertTrue(structure.is_periodic())
        self.assertTrue(structure.is_symmetric())
        self.assertEqual(structure.num_atoms(), 8)
    
    def test_create_molecular_structure(self):
        """Test creating a molecular structure"""
        atom_sites = [
            AtomSite(8, (0.0, 0.0, 0.0), AtomicProperties(charge=-0.8)),
            AtomSite(1, (0.76, 0.59, 0.0), AtomicProperties(charge=0.4)),
            AtomSite(1, (-0.76, 0.59, 0.0), AtomicProperties(charge=0.4))
        ]
        
        structure = USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=atom_sites,
            structure_properties=StructureProperties(energy=-76.4),
            formula="H2O"
        )
        
        self.assertEqual(structure.formula, "H2O")
        self.assertTrue(structure.is_molecular())
        self.assertEqual(structure.num_atoms(), 3)
    
    def test_encode_decode_roundtrip(self):
        """Test encoding and decoding with modular structure"""
        lattice = np.eye(3) * 5.0
        wyckoff_sites = [WyckoffSite(14, 2, (0.0, 0.0, 0.0))]
        
        structure = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice,
            spacegroup=227,
            wyckoff_sites=wyckoff_sites,
            formula="Si"
        )
        
        encoder = USIF(compression=CompressionType.GZIP)
        encoded = encoder.encode(structure)
        decoded, _ = encoder.decode(encoded)
        
        self.assertEqual(structure, decoded)
        self.assertEqual(structure.formula, decoded.formula)
    
    def test_property_system(self):
        """Test property system with modular structure"""
        from usif import PropertyRegistry, PropertyDefinition
        
        # Test built-in properties
        force_def = PropertyRegistry.get('force')
        self.assertIsNotNone(force_def)
        self.assertTrue(force_def.is_per_atom)
        
        energy_def = PropertyRegistry.get('energy')
        self.assertIsNotNone(energy_def)
        self.assertFalse(energy_def.is_per_atom)
        
        # Test custom property registration
        custom_prop = PropertyDefinition(
            name="test_prop",
            data_type=float,
            description="Test property"
        )
        PropertyRegistry.register(custom_prop)
        
        retrieved = PropertyRegistry.get('test_prop')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "test_prop")


if __name__ == '__main__':
    unittest.main()

