#!/usr/bin/env python3
"""
USIF Benchmark Module

This module provides benchmarking utilities for measuring compression ratios,
encoding/decoding performance, and comparing different storage modes.

Main Class:
    USIFBenchmark: Benchmark compression and performance

Features:
    - Compression ratio benchmarking
    - Encoding/decoding speed measurement
    - Comparison of storage modes
    - File size analysis
    - Performance metrics

Usage:
    >>> from usif import USIFBenchmark, USIFStructure
    >>>
    >>> # Create benchmark instance
    >>> benchmark = USIFBenchmark()
    >>>
    >>> # Benchmark compression
    >>> results = benchmark.benchmark_compression(structure)
    >>> print(f"Compression ratio: {results['compression_ratio']:.2f}x")
    >>> print(f"Original size: {results['original_size']} bytes")
    >>> print(f"Compressed size: {results['compressed_size']} bytes")
    >>>
    >>> # Benchmark encoding/decoding speed
    >>> speed_results = benchmark.benchmark_speed(structure)
    >>> print(f"Encode time: {speed_results['encode_time']:.4f}s")
    >>> print(f"Decode time: {speed_results['decode_time']:.4f}s")

See Also:
    - USIFStructure: Structure to benchmark
    - USIF: Encoder/decoder
    - CompressionType: Compression algorithms
"""

import logging
import time
from typing import Any, Dict, List

import numpy as np

from usif.converter import StructureConverter
from usif.encoder import USIF
from usif.structures.structure import USIFStructure

logger = logging.getLogger(__name__)

class USIFBenchmark:
    """Benchmarking utilities for USIF performance"""

    @staticmethod
    def benchmark_compression(structures: List[USIFStructure]) -> Dict[str, Any]:
        """
        Benchmark compression performance for structures

        Measures compression ratios, encoding/decoding speeds, and file sizes
        for a list of structures. Useful for evaluating storage efficiency.

        Args:
            structures: List of USIFStructure instances to benchmark

        Returns:
            Dict[str, Any]: Dictionary containing:
                - compression_ratio: Average compression ratio
                - total_original_size: Total uncompressed size (bytes)
                - total_compressed_size: Total compressed size (bytes)
                - avg_compression_time: Average encoding time (seconds)
                - avg_decompression_time: Average decoding time (seconds)
                - num_structures: Number of structures benchmarked

        Example:
            >>> benchmark = USIFBenchmark()
            >>> structures = [structure1, structure2, structure3]
            >>> results = benchmark.benchmark_compression(structures)
            >>> print(f"Compression ratio: {results['compression_ratio']:.2f}x")
            >>> print(f"Avg encode time: {results['avg_compression_time']:.4f}s")
        """
        encoder = USIF()

        total_original_size = 0
        total_compressed_size = 0
        compression_times = []
        decompression_times = []

        for structure in structures:
            try:
                start = time.time()
                compressed = encoder.encode(structure)
                compression_times.append(time.time() - start)

                start = time.time()
                decoded, _ = encoder.decode(compressed)
                decompression_times.append(time.time() - start)

                pmg_structure = StructureConverter.to_pymatgen(structure)
                cif_size = len(pmg_structure.to(fmt="cif"))
                total_original_size += cif_size
                total_compressed_size += len(compressed)
            except Exception as e:
                logger.error(f"Benchmark error for structure: {e}")
                continue

        avg_compression_ratio = total_compressed_size / total_original_size \
                               if total_original_size > 0 else 0
        avg_compression_time = np.mean(compression_times) if compression_times else 0
        avg_decompression_time = np.mean(decompression_times) if decompression_times else 0

        return {
            'num_structures': len(structures),
            'total_original_size': total_original_size,
            'total_compressed_size': total_compressed_size,
            'average_compression_ratio': avg_compression_ratio,
            'average_compression_time': avg_compression_time,
            'average_decompression_time': avg_decompression_time,
            'compression_speedup': 1.0 / avg_compression_ratio if avg_compression_ratio > 0 else 0
        }
