#!/usr/bin/env python3
"""
USIF Exceptions Module

This module defines the exception hierarchy for the USIF format.
All exceptions inherit from USIFError for easy catching.

Exception Hierarchy:
    USIFError: Base exception for all USIF errors
        EncodingError: Errors during encoding
        DecodingError: Errors during decoding
            CorruptedDataError: Corrupted or invalid data
        ValidationError: Validation errors
        SymmetryAnalysisError: Symmetry analysis errors
        StorageError: Storage/container errors

Usage:
    >>> from usif import USIFError, EncodingError, DecodingError
    >>>
    >>> try:
    ...     structure.save('file.usif')
    ... except EncodingError as e:
    ...     print(f"Encoding failed: {e}")
    ... except USIFError as e:
    ...     print(f"USIF error: {e}")

See Also:
    - USIF: Raises EncodingError and DecodingError
    - StructureContainer: Raises StorageError
    - PropertySerializer: Raises EncodingError and DecodingError
"""


class USIFError(Exception):
    """Base exception for USIF"""
    pass


class EncodingError(USIFError):
    """Error during encoding"""
    pass


class DecodingError(USIFError):
    """Error during decoding"""
    pass


class ValidationError(USIFError):
    """Validation error"""
    pass


class CorruptedDataError(DecodingError):
    """Corrupted data error"""
    pass


class SymmetryAnalysisError(USIFError):
    """Symmetry analysis error"""
    pass


class StorageError(USIFError):
    """Storage error"""
    pass
