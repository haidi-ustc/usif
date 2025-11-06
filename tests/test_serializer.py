#!/usr/bin/env python3
"""
Tests for USIF PropertySerializer
Test serialization and deserialization of properties
"""

import unittest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from usif.properties.serializer import PropertySerializer
from usif.properties.definitions import PropertyDefinition
from usif.exceptions import EncodingError, DecodingError


class TestPropertySerializer(unittest.TestCase):
    """Test PropertySerializer class"""
    
    def test_serialize_scalar_float(self):
        """Test serializing scalar float"""
        prop_def = PropertyDefinition(name="energy", data_type=float)
        value = 10.5
        data = PropertySerializer.serialize_value(value, prop_def)
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)
        
        # Deserialize
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0)
        self.assertAlmostEqual(decoded, value, places=5)
    
    def test_serialize_scalar_int(self):
        """Test serializing scalar int"""
        prop_def = PropertyDefinition(name="count", data_type=int)
        value = 42
        data = PropertySerializer.serialize_value(value, prop_def)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0)
        self.assertEqual(decoded, value)
    
    def test_serialize_scalar_string(self):
        """Test serializing scalar string"""
        prop_def = PropertyDefinition(name="name", data_type=str)
        value = "test_string"
        data = PropertySerializer.serialize_value(value, prop_def)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0)
        self.assertEqual(decoded, value)
    
    def test_serialize_multi_dimensional(self):
        """Test serializing multi-dimensional value"""
        prop_def = PropertyDefinition(
            name="force",
            data_type=tuple,
            dimensions=(3,)
        )
        value = (1.0, 2.0, 3.0)
        data = PropertySerializer.serialize_value(value, prop_def)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0)
        self.assertEqual(len(decoded), 3)
        for i in range(3):
            self.assertAlmostEqual(decoded[i], value[i], places=5)
    
    def test_serialize_per_atom_scalar(self):
        """Test serializing per-atom scalar property"""
        prop_def = PropertyDefinition(
            name="charge",
            data_type=float,
            is_per_atom=True
        )
        value = 0.5  # Single value for all atoms
        data = PropertySerializer.serialize_value(value, prop_def, num_atoms=3)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0, num_atoms=3)
        self.assertEqual(len(decoded), 3)
        self.assertAlmostEqual(decoded[0], value, places=5)
    
    def test_serialize_per_atom_array(self):
        """Test serializing per-atom array property"""
        prop_def = PropertyDefinition(
            name="charge",
            data_type=float,
            is_per_atom=True
        )
        value = [0.5, 0.6, 0.7]  # Different value for each atom
        data = PropertySerializer.serialize_value(value, prop_def, num_atoms=3)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0, num_atoms=3)
        self.assertEqual(len(decoded), 3)
        for i in range(3):
            self.assertAlmostEqual(decoded[i], value[i], places=5)
    
    def test_serialize_per_atom_multi_dimensional(self):
        """Test serializing per-atom multi-dimensional property"""
        prop_def = PropertyDefinition(
            name="force",
            data_type=tuple,
            is_per_atom=True,
            dimensions=(3,)
        )
        value = (1.0, 2.0, 3.0)  # Single force vector
        data = PropertySerializer.serialize_value(value, prop_def, num_atoms=1)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0, num_atoms=1)
        self.assertEqual(decoded, value)
    
    def test_serialize_structure_array(self):
        """Test serializing structure-level array property"""
        prop_def = PropertyDefinition(
            name="stress",
            data_type=tuple,
            dimensions=(6,)
        )
        value = (1.0, 1.0, 1.0, 0.0, 0.0, 0.0)
        data = PropertySerializer.serialize_value(value, prop_def)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0)
        self.assertEqual(len(decoded), 6)
        for i in range(6):
            self.assertAlmostEqual(decoded[i], value[i], places=5)
    
    def test_serialize_none_value(self):
        """Test serializing None value"""
        prop_def = PropertyDefinition(name="energy", data_type=float)
        data = PropertySerializer.serialize_value(None, prop_def)
        self.assertEqual(data, b'')
    
    def test_deserialize_empty_data(self):
        """Test deserializing from empty data"""
        prop_def = PropertyDefinition(name="energy", data_type=float)
        value, offset = PropertySerializer.deserialize_value(prop_def, b'', 0)
        self.assertIsNone(value)
        self.assertEqual(offset, 0)
    
    def test_serialize_long_string(self):
        """Test serializing long string (>255 chars)"""
        prop_def = PropertyDefinition(name="description", data_type=str)
        value = "a" * 300
        data = PropertySerializer.serialize_value(value, prop_def)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0)
        self.assertEqual(decoded, value)
    
    def test_serialize_per_atom_list_of_vectors(self):
        """Test serializing list of vectors for per-atom property"""
        prop_def = PropertyDefinition(
            name="force",
            data_type=tuple,
            is_per_atom=True,
            dimensions=(3,)
        )
        value = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        data = PropertySerializer.serialize_value(value, prop_def, num_atoms=2)
        
        decoded, offset = PropertySerializer.deserialize_value(prop_def, data, 0, num_atoms=2)
        self.assertEqual(len(decoded), 2)
        for i in range(2):
            for j in range(3):
                self.assertAlmostEqual(decoded[i][j], value[i][j], places=5)


if __name__ == '__main__':
    unittest.main()

