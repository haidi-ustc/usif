#!/usr/bin/env python3
"""
USIF Utils Module

This module provides utility functions for structure optimization and benchmarking.

Main Classes:
    USIFOptimizer: Optimize structures for maximum compression
    USIFBenchmark: Benchmark compression and performance

Features:
    - Automatic symmetry analysis and optimization
    - Compression ratio benchmarking
    - Performance metrics

Usage:
    >>> from usif import USIFOptimizer, USIFStructure
    >>> 
    >>> # Optimize structure for compression
    >>> optimizer = USIFOptimizer()
    >>> optimized = optimizer.optimize_structure(structure)
    >>> 
    >>> # Benchmark compression
    >>> from usif import USIFBenchmark
    >>> benchmark = USIFBenchmark()
    >>> results = benchmark.benchmark_compression(structure)

See Also:
    - USIFStructure: Structure to optimize
    - StructureConverter: Conversion utilities
"""

from .optimizer import USIFOptimizer
from .benchmark import USIFBenchmark

__all__ = [
    'USIFOptimizer',
    'USIFBenchmark',
]

