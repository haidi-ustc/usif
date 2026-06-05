#!/usr/bin/env python3
"""
USIF Utils Module

This module provides utility functions for structure optimization, benchmarking,
and Materials Project data handling.

Main Classes:
    USIFOptimizer: Optimize structures for maximum compression
    USIFBenchmark: Benchmark compression and performance

Main Functions:
    download_mp_data: Download Materials Project structures
    load_mp_group: Load MP data from JSON files
    convert_mp_to_usif: Convert MP documents to USIF structures
    create_mp_data_archive: Create zip archive of MP data
    load_mp_data_from_archive: Load MP data from zip archive

Features:
    - Automatic symmetry analysis and optimization
    - Compression ratio benchmarking
    - Performance metrics
    - Materials Project data download and conversion

Usage:
    >>> from usif import USIFStructure
    >>> from usif.utils import USIFOptimizer
    >>>
    >>> # Optimize structure for compression
    >>> optimizer = USIFOptimizer()
    >>> optimized = optimizer.optimize_structure(structure)
    >>>
    >>> # Benchmark compression
    >>> from usif.utils import USIFBenchmark
    >>> benchmark = USIFBenchmark()
    >>> results = benchmark.benchmark_compression(structure)
    >>>
    >>> # Download and convert MP data
    >>> from usif.utils import download_mp_data, convert_mp_to_usif
    >>> stats = download_mp_data(api_key="YOUR_KEY")
    >>> usif_struct = convert_mp_to_usif(mp_doc)

See Also:
    - USIFStructure: Structure to optimize
    - PymatgenImporter/PymatgenExporter: Conversion utilities
"""

from .benchmark import USIFBenchmark
from .optimizer import USIFOptimizer

# Convenience aliases exported in __all__.
optimize_structure = USIFOptimizer.optimize_structure
benchmark_compression = USIFBenchmark.benchmark_compression

_MP_EXPORTS = {
    "convert_mp_to_usif",
    "create_mp_data_archive",
    "download_mp_data",
    "load_mp_data_from_archive",
    "load_mp_group",
}


def __getattr__(name):
    if name in _MP_EXPORTS:
        from . import mp_downloader

        value = getattr(mp_downloader, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "USIFOptimizer",
    "optimize_structure",
    "USIFBenchmark",
    "benchmark_compression",
    "download_mp_data",
    "load_mp_group",
    "convert_mp_to_usif",
    "create_mp_data_archive",
    "load_mp_data_from_archive",
]
