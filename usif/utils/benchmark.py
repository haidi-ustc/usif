#!/usr/bin/env python3
"""
USIF Benchmark
Performance benchmarking utilities
"""

import time
import logging
import numpy as np
from typing import List, Dict, Any

from usif.encoder import USIF
from usif.structures.structure import USIFStructure
from usif.converter import StructureConverter

logger = logging.getLogger(__name__)

class USIFBenchmark:
    """Benchmarking utilities for USIF performance"""
    
    @staticmethod
    def benchmark_compression(structures: List[USIFStructure]) -> Dict[str, Any]:
        """
        Benchmark compression performance
        
        Args:
            structures: List of structures to benchmark
            
        Returns:
            Dictionary with benchmark results
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


# ============================================================================
# Main Usage Examples
# ============================================================================

