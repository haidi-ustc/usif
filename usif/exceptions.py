#!/usr/bin/env python3
"""
USIF Exceptions
Exception hierarchy for USIF format
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

