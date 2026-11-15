"""Compression and round-trip benchmark helpers."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List

import numpy as np

from usif.encoder import USIF
from usif.services.json_io import structure_to_json_dict
from usif.structures.structure import USIFStructure

logger = logging.getLogger(__name__)


class USIFBenchmark:
    """Benchmark USIF compression and encode/decode throughput."""

    @staticmethod
    def benchmark_compression(structures: List[USIFStructure]) -> Dict[str, Any]:
        """Benchmark compression performance for a list of structures."""
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
                encoder.decode(compressed)
                decompression_times.append(time.time() - start)

                # Baseline: the uncompressed official USIF JSON document,
                # which needs no external structure library.
                text_size = len(json.dumps(structure_to_json_dict(structure)).encode("utf-8"))
                total_original_size += text_size
                total_compressed_size += len(compressed)
            except Exception as e:
                logger.debug("Benchmark skipped structure: %s", e)
                continue

        average_compression_ratio = (
            total_compressed_size / total_original_size if total_original_size > 0 else 0
        )
        average_compression_time = float(np.mean(compression_times)) if compression_times else 0
        average_decompression_time = (
            float(np.mean(decompression_times)) if decompression_times else 0
        )

        return {
            "num_structures": len(structures),
            "total_original_size": total_original_size,
            "total_compressed_size": total_compressed_size,
            "average_compression_ratio": average_compression_ratio,
            "average_compression_time": average_compression_time,
            "average_decompression_time": average_decompression_time,
            "compression_speedup": (
                1.0 / average_compression_ratio if average_compression_ratio > 0 else 0
            ),
        }


def benchmark_compression(structures: List[USIFStructure]) -> Dict[str, Any]:
    """Functional entry point for compression benchmarks."""
    return USIFBenchmark.benchmark_compression(structures)
