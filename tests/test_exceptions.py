#!/usr/bin/env python3
"""
Test exceptions module
"""

import sys
import unittest
import importlib.util
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly from module file to avoid triggering __init__.py
spec = importlib.util.spec_from_file_location(
    "exceptions", Path(__file__).parent.parent / "usif" / "exceptions.py"
)
exceptions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exceptions)

CorruptedDataError = exceptions.CorruptedDataError
DecodingError = exceptions.DecodingError
EncodingError = exceptions.EncodingError
StorageError = exceptions.StorageError
SymmetryAnalysisError = exceptions.SymmetryAnalysisError
USIFError = exceptions.USIFError
ValidationError = exceptions.ValidationError


class TestExceptionHierarchy(unittest.TestCase):
    """Test exception class hierarchy"""

    def test_usif_error_is_base(self):
        """Test that USIFError is the base exception"""
        self.assertTrue(issubclass(EncodingError, USIFError))
        self.assertTrue(issubclass(DecodingError, USIFError))
        self.assertTrue(issubclass(ValidationError, USIFError))
        self.assertTrue(issubclass(SymmetryAnalysisError, USIFError))
        self.assertTrue(issubclass(StorageError, USIFError))
        self.assertTrue(issubclass(CorruptedDataError, USIFError))

    def test_decoding_error_inheritance(self):
        """Test that CorruptedDataError inherits from DecodingError"""
        self.assertTrue(issubclass(CorruptedDataError, DecodingError))
        self.assertTrue(issubclass(CorruptedDataError, USIFError))

    def test_exception_instantiation(self):
        """Test that exceptions can be instantiated"""
        # Base exception
        error = USIFError("Test error")
        self.assertIsInstance(error, Exception)
        self.assertEqual(str(error), "Test error")

        # Derived exceptions
        encoding_error = EncodingError("Encoding failed")
        self.assertIsInstance(encoding_error, USIFError)
        self.assertEqual(str(encoding_error), "Encoding failed")

        decoding_error = DecodingError("Decoding failed")
        self.assertIsInstance(decoding_error, USIFError)
        self.assertEqual(str(decoding_error), "Decoding failed")

        validation_error = ValidationError("Validation failed")
        self.assertIsInstance(validation_error, USIFError)
        self.assertEqual(str(validation_error), "Validation failed")

        corrupted_error = CorruptedDataError("Data corrupted")
        self.assertIsInstance(corrupted_error, DecodingError)
        self.assertIsInstance(corrupted_error, USIFError)
        self.assertEqual(str(corrupted_error), "Data corrupted")

        symmetry_error = SymmetryAnalysisError("Symmetry analysis failed")
        self.assertIsInstance(symmetry_error, USIFError)
        self.assertEqual(str(symmetry_error), "Symmetry analysis failed")

        storage_error = StorageError("Storage failed")
        self.assertIsInstance(storage_error, USIFError)
        self.assertEqual(str(storage_error), "Storage failed")

    def test_exception_catching(self):
        """Test exception catching hierarchy"""
        # Test that catching USIFError catches all
        try:
            raise EncodingError("Test")
        except USIFError as e:
            self.assertIsInstance(e, EncodingError)
            self.assertEqual(str(e), "Test")

        # Test that catching DecodingError catches CorruptedDataError
        try:
            raise CorruptedDataError("Test")
        except DecodingError as e:
            self.assertIsInstance(e, CorruptedDataError)
            self.assertEqual(str(e), "Test")

        # Test that catching USIFError catches CorruptedDataError
        try:
            raise CorruptedDataError("Test")
        except USIFError as e:
            self.assertIsInstance(e, CorruptedDataError)
            self.assertEqual(str(e), "Test")

    def test_exception_with_no_message(self):
        """Test exceptions can be raised without message"""
        try:
            raise USIFError()
        except USIFError:
            pass

        try:
            raise EncodingError()
        except EncodingError:
            pass

        try:
            raise DecodingError()
        except DecodingError:
            pass

    def test_exception_attributes(self):
        """Test that exceptions can have custom attributes"""
        error = EncodingError("Test message")
        error.code = 100
        self.assertEqual(error.code, 100)
        self.assertEqual(str(error), "Test message")


if __name__ == "__main__":
    unittest.main()

