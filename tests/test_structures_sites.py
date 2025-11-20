#!/usr/bin/env python3
"""
Tests for USIF structures sites module
Test WyckoffSite, PointGroupSite, AtomSite
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from usif.properties.atomic import AtomicProperties
from usif.structures.sites import AtomSite, PointGroupSite, WyckoffSite


class TestWyckoffSite(unittest.TestCase):
    """Test WyckoffSite class"""

    def test_create_wyckoff_site(self):
        """Test creating Wyckoff site"""
        site = WyckoffSite(
            atomic_number=14,
            multiplicity=8,
            coords=(0.0, 0.0, 0.0),
            occupancy=1.0
        )
        self.assertEqual(site.atomic_number, 14)
        self.assertEqual(site.multiplicity, 8)
        self.assertEqual(site.coords, (0.0, 0.0, 0.0))
        self.assertEqual(site.occupancy, 1.0)

    def test_default_occupancy(self):
        """Test default occupancy value"""
        site = WyckoffSite(14, 8, (0.0, 0.0, 0.0))
        self.assertEqual(site.occupancy, 1.0)

    def test_equality(self):
        """Test site equality"""
        site1 = WyckoffSite(14, 8, (0.0, 0.0, 0.0), 1.0)
        site2 = WyckoffSite(14, 8, (0.0, 0.0, 0.0), 1.0)
        self.assertEqual(site1, site2)

        site3 = WyckoffSite(14, 8, (0.1, 0.0, 0.0), 1.0)
        self.assertNotEqual(site1, site3)

    def test_equality_with_tolerance(self):
        """Test equality with floating point tolerance"""
        site1 = WyckoffSite(14, 8, (0.5, 0.5, 0.5), 1.0)
        site2 = WyckoffSite(14, 8, (0.5000001, 0.5, 0.5), 1.0)
        self.assertEqual(site1, site2)  # Should be equal within tolerance


class TestPointGroupSite(unittest.TestCase):
    """Test PointGroupSite class"""

    def test_create_point_group_site(self):
        """Test creating point group site"""
        site = PointGroupSite(
            atomic_number=8,
            multiplicity=1,
            coords=(0.0, 0.0, 0.0),
            occupancy=1.0
        )
        self.assertEqual(site.atomic_number, 8)
        self.assertEqual(site.multiplicity, 1)
        self.assertEqual(site.coords, (0.0, 0.0, 0.0))
        self.assertEqual(site.occupancy, 1.0)

    def test_default_occupancy(self):
        """Test default occupancy value"""
        site = PointGroupSite(8, 1, (0.0, 0.0, 0.0))
        self.assertEqual(site.occupancy, 1.0)

    def test_equality(self):
        """Test site equality"""
        site1 = PointGroupSite(8, 1, (0.0, 0.0, 0.0), 1.0)
        site2 = PointGroupSite(8, 1, (0.0, 0.0, 0.0), 1.0)
        self.assertEqual(site1, site2)

        site3 = PointGroupSite(8, 2, (0.0, 0.0, 0.0), 1.0)
        self.assertNotEqual(site1, site3)

    def test_equality_with_tolerance(self):
        """Test equality with floating point tolerance"""
        site1 = PointGroupSite(8, 1, (0.76, 0.59, 0.0), 1.0)
        site2 = PointGroupSite(8, 1, (0.7600001, 0.59, 0.0), 1.0)
        self.assertEqual(site1, site2)  # Should be equal within tolerance


class TestAtomSite(unittest.TestCase):
    """Test AtomSite class"""

    def test_create_atom_site(self):
        """Test creating atom site"""
        site = AtomSite(
            atomic_number=14,
            coords=(0.0, 0.0, 0.0)
        )
        self.assertEqual(site.atomic_number, 14)
        self.assertEqual(site.coords, (0.0, 0.0, 0.0))
        self.assertIsNotNone(site.properties)

    def test_create_with_properties(self):
        """Test creating atom site with properties"""
        props = AtomicProperties(charge=0.5, force=(1.0, 2.0, 3.0))
        site = AtomSite(14, (0.0, 0.0, 0.0), props)
        self.assertEqual(site.properties, props)
        self.assertEqual(site.properties.charge, 0.5)

    def test_default_properties(self):
        """Test default properties"""
        site = AtomSite(14, (0.0, 0.0, 0.0))
        self.assertIsInstance(site.properties, AtomicProperties)
        self.assertIsNone(site.properties.charge)

    def test_equality(self):
        """Test site equality"""
        site1 = AtomSite(14, (0.0, 0.0, 0.0))
        site2 = AtomSite(14, (0.0, 0.0, 0.0))
        self.assertEqual(site1, site2)

        site3 = AtomSite(14, (0.1, 0.0, 0.0))
        self.assertNotEqual(site1, site3)

    def test_equality_with_properties(self):
        """Test equality with properties"""
        props1 = AtomicProperties(charge=0.5)
        props2 = AtomicProperties(charge=0.5)
        site1 = AtomSite(14, (0.0, 0.0, 0.0), props1)
        site2 = AtomSite(14, (0.0, 0.0, 0.0), props2)
        self.assertEqual(site1, site2)

        props3 = AtomicProperties(charge=0.6)
        site3 = AtomSite(14, (0.0, 0.0, 0.0), props3)
        self.assertNotEqual(site1, site3)

    def test_equality_with_tolerance(self):
        """Test equality with floating point tolerance"""
        site1 = AtomSite(14, (0.5, 0.5, 0.5))
        site2 = AtomSite(14, (0.5000001, 0.5, 0.5))
        self.assertEqual(site1, site2)  # Should be equal within tolerance


if __name__ == '__main__':
    unittest.main()
