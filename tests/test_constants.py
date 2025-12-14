#!/usr/bin/env python3
"""
Test constants module
"""

import struct
import sys
import unittest
import importlib.util
from pathlib import Path

# Ensure conftest is loaded (sets up path) - works for both unittest and pytest
# Add tests directory to path to import conftest
tests_dir = Path(__file__).parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))
try:
    import conftest  # noqa: F401
except ImportError:
    # If conftest import fails, set up path manually
    project_root = tests_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# Import directly from module file to avoid triggering __init__.py
spec = importlib.util.spec_from_file_location(
    "constants", tests_dir.parent / "usif" / "constants.py"
)
constants = importlib.util.module_from_spec(spec)
spec.loader.exec_module(constants)

BinaryFormat = constants.BinaryFormat
CompressionType = constants.CompressionType
StorageMode = constants.StorageMode
StructureType = constants.StructureType
SymmetryConstants = constants.SymmetryConstants


class TestEnumerations(unittest.TestCase):
    """Test enumeration types"""

    def test_structure_type(self):
        """Test StructureType enumeration"""
        self.assertEqual(StructureType.CRYSTAL, 0)
        self.assertEqual(StructureType.MOLECULE, 1)
        self.assertIsInstance(StructureType.CRYSTAL, int)
        self.assertIsInstance(StructureType.MOLECULE, int)

    def test_storage_mode(self):
        """Test StorageMode enumeration"""
        self.assertEqual(StorageMode.SYMMETRIC, 0)
        self.assertEqual(StorageMode.FULL_ATOMIC, 1)
        self.assertIsInstance(StorageMode.SYMMETRIC, int)
        self.assertIsInstance(StorageMode.FULL_ATOMIC, int)

    def test_compression_type(self):
        """Test CompressionType enumeration"""
        self.assertEqual(CompressionType.NONE, 0)
        self.assertEqual(CompressionType.GZIP, 1)
        self.assertIsInstance(CompressionType.NONE, int)
        self.assertIsInstance(CompressionType.GZIP, int)

    def test_enum_comparison(self):
        """Test enum comparison"""
        self.assertEqual(StructureType.CRYSTAL, 0)
        self.assertNotEqual(StructureType.CRYSTAL, StructureType.MOLECULE)
        self.assertTrue(StructureType.CRYSTAL < StructureType.MOLECULE)


class TestBinaryFormat(unittest.TestCase):
    """Test BinaryFormat constants"""

    def test_unsigned_integers(self):
        """Test unsigned integer formats"""
        self.assertEqual(BinaryFormat.UINT8, "<B")
        self.assertEqual(BinaryFormat.UINT16, "<H")
        self.assertEqual(BinaryFormat.UINT32, "<I")
        self.assertEqual(BinaryFormat.UINT64, "<Q")

    def test_signed_integers(self):
        """Test signed integer formats"""
        self.assertEqual(BinaryFormat.INT8, "<b")
        self.assertEqual(BinaryFormat.INT16, "<h")
        self.assertEqual(BinaryFormat.INT32, "<i")
        self.assertEqual(BinaryFormat.INT64, "<q")

    def test_floating_point(self):
        """Test floating point formats"""
        self.assertEqual(BinaryFormat.FLOAT32, "<f")
        self.assertEqual(BinaryFormat.FLOAT64, "<d")

    def test_boolean(self):
        """Test boolean format"""
        self.assertEqual(BinaryFormat.BOOL, "<?")

    def test_special_flags(self):
        """Test special flag constants"""
        self.assertEqual(BinaryFormat.LONG_COUNT_FLAG, 0xFF)
        self.assertEqual(BinaryFormat.NULL_FLAG, 0xFE)
        self.assertEqual(BinaryFormat.NAN_FLAG, 0xFD)

    def test_array_method(self):
        """Test array format string generation"""
        # Test with standard format
        result = BinaryFormat.array(BinaryFormat.FLOAT32, 3)
        self.assertEqual(result, "3f")

        # Test with format that has endianness
        result = BinaryFormat.array(BinaryFormat.UINT32, 5)
        self.assertEqual(result, "5I")

        # Test with count
        result = BinaryFormat.array(BinaryFormat.INT16, 10)
        self.assertEqual(result, "10h")

    def test_array_method_strips_endianness(self):
        """Test that array method strips endianness prefix"""
        result = BinaryFormat.array("<f", 3)
        self.assertEqual(result, "3f")

        result = BinaryFormat.array(">d", 2)
        self.assertEqual(result, "2d")

        result = BinaryFormat.array("=I", 4)
        self.assertEqual(result, "4I")

    def test_binary_format_usage(self):
        """Test actual usage of binary formats"""
        # Test packing/unpacking
        data = struct.pack(BinaryFormat.FLOAT32, 3.14)
        value = struct.unpack(BinaryFormat.FLOAT32, data)[0]
        self.assertAlmostEqual(value, 3.14, places=5)

        # Test integer packing
        data = struct.pack(BinaryFormat.UINT32, 42)
        value = struct.unpack(BinaryFormat.UINT32, data)[0]
        self.assertEqual(value, 42)

        # Test array packing
        fmt = BinaryFormat.array(BinaryFormat.FLOAT32, 3)
        data = struct.pack(fmt, 1.0, 2.0, 3.0)
        values = struct.unpack(fmt, data)
        self.assertEqual(len(values), 3)
        self.assertAlmostEqual(values[0], 1.0)
        self.assertAlmostEqual(values[1], 2.0)
        self.assertAlmostEqual(values[2], 3.0)


class TestSymmetryConstants(unittest.TestCase):
    """Test SymmetryConstants"""

    def test_default_symmetry_tolerance(self):
        """Test default symmetry tolerance"""
        self.assertEqual(SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE, 1e-3)
        self.assertIsInstance(SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE, float)

    def test_default_symmetry_precision(self):
        """Test default symmetry precision"""
        self.assertEqual(SymmetryConstants.DEFAULT_SYMMETRY_PRECISION, 0.1)
        self.assertIsInstance(SymmetryConstants.DEFAULT_SYMMETRY_PRECISION, float)

    def test_molecular_equivalence_threshold(self):
        """Test molecular equivalence threshold"""
        self.assertEqual(
            SymmetryConstants.MOLECULAR_EQUIVALENCE_THRESHOLD, 0.01
        )
        self.assertIsInstance(
            SymmetryConstants.MOLECULAR_EQUIVALENCE_THRESHOLD, float
        )

    def test_property_value_tolerance(self):
        """Test property value tolerance"""
        self.assertEqual(SymmetryConstants.PROPERTY_VALUE_TOLERANCE, 0.001)
        self.assertIsInstance(SymmetryConstants.PROPERTY_VALUE_TOLERANCE, float)

    def test_coordinate_tolerance(self):
        """Test coordinate tolerance"""
        self.assertEqual(SymmetryConstants.COORDINATE_TOLERANCE, 1e-6)
        self.assertIsInstance(SymmetryConstants.COORDINATE_TOLERANCE, float)

    def test_tolerance_hierarchy(self):
        """Test that tolerances are in expected hierarchy"""
        # Coordinate tolerance should be tightest
        self.assertLess(
            SymmetryConstants.COORDINATE_TOLERANCE,
            SymmetryConstants.PROPERTY_VALUE_TOLERANCE,
        )
        # Property tolerance should be less than or equal to symmetry tolerance
        self.assertLessEqual(
            SymmetryConstants.PROPERTY_VALUE_TOLERANCE,
            SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE,
        )
        # Coordinate tolerance should be much tighter than symmetry tolerance
        self.assertLess(
            SymmetryConstants.COORDINATE_TOLERANCE,
            SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE,
        )


if __name__ == "__main__":
    unittest.main()

