#!/usr/bin/env python3
"""
Tests for USIF properties module
Test PropertyDefinition, PropertyRegistry, AtomicProperties, StructureProperties
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from usif.exceptions import ValidationError
from usif.properties.atomic import AtomicProperties
from usif.properties.definitions import PropertyDefinition
from usif.properties.registry import PropertyRegistry
from usif.properties.structure import StructureProperties


class TestPropertyDefinition(unittest.TestCase):
    """Test PropertyDefinition class"""

    def test_scalar_property_definition(self):
        """Test scalar property definition"""
        prop_def = PropertyDefinition(
            name="energy",
            data_type=float,
            description="Total energy",
            units="eV"
        )
        self.assertTrue(prop_def.is_scalar())
        self.assertEqual(prop_def.name, "energy")
        self.assertEqual(prop_def.data_type, float)

    def test_array_property_definition(self):
        """Test array property definition"""
        prop_def = PropertyDefinition(
            name="force",
            data_type=tuple,
            is_per_atom=True,
            dimensions=(3,),
            description="Force vector"
        )
        self.assertFalse(prop_def.is_scalar())
        self.assertEqual(prop_def.dimensions, (3,))

    def test_validate_scalar_value(self):
        """Test scalar value validation"""
        prop_def = PropertyDefinition(name="energy", data_type=float)
        is_valid, msg = prop_def.validate_value(10.5)
        self.assertTrue(is_valid)

        is_valid, msg = prop_def.validate_value("invalid")
        self.assertFalse(is_valid)

    def test_validate_array_value(self):
        """Test array value validation"""
        prop_def = PropertyDefinition(
            name="force",
            data_type=tuple,
            dimensions=(3,)
        )
        is_valid, msg = prop_def.validate_value((1.0, 2.0, 3.0))
        self.assertTrue(is_valid)

        is_valid, msg = prop_def.validate_value((1.0, 2.0))  # Wrong length
        self.assertFalse(is_valid)

    def test_validate_with_range(self):
        """Test validation with min/max values"""
        prop_def = PropertyDefinition(
            name="temperature",
            data_type=float,
            min_value=0.0,
            max_value=1000.0
        )
        is_valid, msg = prop_def.validate_value(500.0)
        self.assertTrue(is_valid)

        is_valid, msg = prop_def.validate_value(-10.0)
        self.assertFalse(is_valid)

        is_valid, msg = prop_def.validate_value(2000.0)
        self.assertFalse(is_valid)

    def test_get_expected_shape(self):
        """Test expected shape calculation"""
        prop_def = PropertyDefinition(
            name="force",
            data_type=tuple,
            is_per_atom=True,
            dimensions=(3,)
        )
        shape = prop_def.get_expected_shape(num_atoms=10)
        self.assertEqual(shape, (10, 3))

        prop_def2 = PropertyDefinition(
            name="stress",
            data_type=tuple,
            dimensions=(6,)
        )
        shape = prop_def2.get_expected_shape()
        self.assertEqual(shape, (6,))


class TestPropertyRegistry(unittest.TestCase):
    """Test PropertyRegistry class"""

    def test_get_builtin_property(self):
        """Test getting built-in properties"""
        energy_def = PropertyRegistry.get('energy')
        self.assertIsNotNone(energy_def)
        self.assertEqual(energy_def.name, 'energy')
        self.assertFalse(energy_def.is_per_atom)

        force_def = PropertyRegistry.get('force')
        self.assertIsNotNone(force_def)
        self.assertTrue(force_def.is_per_atom)

    def test_register_custom_property(self):
        """Test registering custom property"""
        custom_prop = PropertyDefinition(
            name="custom_prop",
            data_type=float,
            description="Custom property"
        )
        PropertyRegistry.register(custom_prop)

        retrieved = PropertyRegistry.get('custom_prop')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "custom_prop")

    def test_is_atomic_property(self):
        """Test checking if property is atomic"""
        self.assertTrue(PropertyRegistry.is_atomic_property('force'))
        self.assertTrue(PropertyRegistry.is_atomic_property('charge'))
        self.assertFalse(PropertyRegistry.is_atomic_property('energy'))

    def test_is_structure_property(self):
        """Test checking if property is structure-level"""
        self.assertTrue(PropertyRegistry.is_structure_property('energy'))
        self.assertTrue(PropertyRegistry.is_structure_property('volume'))
        self.assertFalse(PropertyRegistry.is_structure_property('force'))


class TestAtomicProperties(unittest.TestCase):
    """Test AtomicProperties class"""

    def test_create_empty_properties(self):
        """Test creating empty atomic properties"""
        props = AtomicProperties()
        self.assertIsNone(props.force)
        self.assertIsNone(props.charge)
        self.assertIsNone(props.magmom)
        self.assertIsNone(props.velocity)
        self.assertEqual(props.custom, {})

    def test_create_with_values(self):
        """Test creating atomic properties with values"""
        props = AtomicProperties(
            force=(1.0, 2.0, 3.0),
            charge=0.5,
            magmom=2.0,
            velocity=(0.1, 0.2, 0.3)
        )
        self.assertEqual(props.force, (1.0, 2.0, 3.0))
        self.assertEqual(props.charge, 0.5)
        self.assertEqual(props.magmom, 2.0)
        self.assertEqual(props.velocity, (0.1, 0.2, 0.3))

    def test_get_all_properties(self):
        """Test getting all properties as dictionary"""
        props = AtomicProperties(charge=0.5, force=(1.0, 2.0, 3.0))
        all_props = props.get_all_properties()
        self.assertIn('charge', all_props)
        self.assertIn('force', all_props)
        self.assertEqual(all_props['charge'], 0.5)
        self.assertEqual(all_props['force'], (1.0, 2.0, 3.0))

    def test_custom_properties(self):
        """Test custom properties"""
        props = AtomicProperties()
        props.custom['custom_key'] = 'custom_value'
        all_props = props.get_all_properties()
        self.assertIn('custom_key', all_props)
        self.assertEqual(all_props['custom_key'], 'custom_value')

    def test_equality(self):
        """Test property equality"""
        props1 = AtomicProperties(charge=0.5, force=(1.0, 2.0, 3.0))
        props2 = AtomicProperties(charge=0.5, force=(1.0, 2.0, 3.0))
        self.assertEqual(props1, props2)

        props3 = AtomicProperties(charge=0.6)
        self.assertNotEqual(props1, props3)

    def test_equality_with_tolerance(self):
        """Test equality with floating point tolerance"""
        props1 = AtomicProperties(charge=0.5)
        props2 = AtomicProperties(charge=0.5000001)  # Very small difference
        self.assertEqual(props1, props2)  # Should be equal within tolerance


class TestStructureProperties(unittest.TestCase):
    """Test StructureProperties class"""

    def test_create_empty_properties(self):
        """Test creating empty structure properties"""
        props = StructureProperties()
        self.assertIsNone(props.energy)
        self.assertIsNone(props.volume)
        self.assertIsNone(props.stress)
        self.assertIsNone(props.pressure)
        self.assertIsNone(props.temperature)
        self.assertEqual(props.custom, {})

    def test_create_with_values(self):
        """Test creating structure properties with values"""
        props = StructureProperties(
            energy=-10.5,
            volume=125.0,
            stress=(1.0, 1.0, 1.0, 0.0, 0.0, 0.0),
            pressure=1.0,
            temperature=300.0
        )
        self.assertEqual(props.energy, -10.5)
        self.assertEqual(props.volume, 125.0)
        self.assertEqual(props.stress, (1.0, 1.0, 1.0, 0.0, 0.0, 0.0))
        self.assertEqual(props.pressure, 1.0)
        self.assertEqual(props.temperature, 300.0)

    def test_get_all_properties(self):
        """Test getting all properties as dictionary"""
        props = StructureProperties(energy=-10.5, volume=125.0)
        all_props = props.get_all_properties()
        self.assertIn('energy', all_props)
        self.assertIn('volume', all_props)
        self.assertEqual(all_props['energy'], -10.5)
        self.assertEqual(all_props['volume'], 125.0)

    def test_custom_properties(self):
        """Test custom properties"""
        props = StructureProperties()
        props.custom['calculator'] = 'VASP'
        all_props = props.get_all_properties()
        self.assertIn('calculator', all_props)
        self.assertEqual(all_props['calculator'], 'VASP')

    def test_equality(self):
        """Test property equality"""
        props1 = StructureProperties(energy=-10.5, volume=125.0)
        props2 = StructureProperties(energy=-10.5, volume=125.0)
        self.assertEqual(props1, props2)

        props3 = StructureProperties(energy=-10.6)
        self.assertNotEqual(props1, props3)

    def test_equality_with_stress(self):
        """Test equality with stress tensor"""
        stress = (1.0, 1.0, 1.0, 0.0, 0.0, 0.0)
        props1 = StructureProperties(stress=stress)
        props2 = StructureProperties(stress=stress)
        self.assertEqual(props1, props2)

    def test_equality_with_tolerance(self):
        """Test equality with floating point tolerance"""
        props1 = StructureProperties(energy=-10.5)
        props2 = StructureProperties(energy=-10.500001)  # Small difference
        self.assertEqual(props1, props2)  # Should be equal within tolerance


if __name__ == '__main__':
    unittest.main()
