#!/usr/bin/env python3
"""
USIF Optimizer Module

This module provides utilities for optimizing structures to achieve maximum
compression by analyzing symmetry and converting to symmetric storage modes
when beneficial.

Main Class:
    USIFOptimizer: Optimize structures for maximum compression

Features:
    - Automatic symmetry analysis using pymatgen
    - Conversion to symmetric storage mode when beneficial
    - Wyckoff site extraction for crystals
    - Point group analysis for molecules
    - Tolerance control for symmetry detection

Requirements:
    - pymatgen: Required dependency for symmetry analysis

Usage:
    >>> from usif import USIFStructure
    >>> from usif.utils import USIFOptimizer
    >>>
    >>> # Create optimizer
    >>> optimizer = USIFOptimizer()
    >>>
    >>> # Optimize structure (may convert to symmetric mode)
    >>> optimized = optimizer.optimize_structure(structure)
    >>>
    >>> # With custom tolerance
    >>> optimized = optimizer.optimize_structure(
    ...     structure,
    ...     tolerance=1e-4  # Stricter symmetry tolerance
    ... )
    >>>
    >>> # Check if optimization changed storage mode
    >>> if optimized.storage_mode != structure.storage_mode:
    ...     print("Storage mode changed during optimization")

Note:
    This module requires pymatgen to be installed as a core dependency.

See Also:
    - USIFStructure: Structure to optimize
    - PymatgenImporter/PymatgenExporter: Conversion utilities
    - SymmetryConstants: Symmetry tolerance constants
"""

import logging

from usif.constants import SymmetryConstants
from usif.structures.structure import USIFStructure
from usif.symmetry.reduce import SymmetryReducer

logger = logging.getLogger(__name__)


class USIFOptimizer:
    """Performance optimization utilities for USIF"""

    @staticmethod
    def optimize_structure(
        structure: USIFStructure,
        tolerance: float = SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE,
    ) -> USIFStructure:
        """
        Optimize structure for maximum compression

        Analyzes structure symmetry and converts to symmetric storage mode if beneficial.
        For crystals, extracts Wyckoff sites. For molecules, extracts point group sites.
        This can significantly reduce file size for symmetric structures.

        Args:
            structure: Input USIFStructure to optimize
            tolerance: Symmetry tolerance for grouping atoms (default: 1e-3)

        Returns:
            USIFStructure: Optimized structure (may have different storage_mode)

        Note:
            Requires pymatgen (core dependency).

        Example:
            >>> optimizer = USIFOptimizer()
            >>> # Optimize with default tolerance
            >>> optimized = optimizer.optimize_structure(structure)
            >>> # Optimize with stricter tolerance
            >>> optimized = optimizer.optimize_structure(structure, tolerance=1e-4)
            >>>
            >>> # Check if storage mode changed
            >>> if optimized.storage_mode != structure.storage_mode:
            ...     print("Converted to symmetric storage mode")
        """
        if structure.is_crystal():
            return USIFOptimizer._optimize_crystal(structure, tolerance)
        else:
            return USIFOptimizer._optimize_molecule(structure, tolerance)

    @staticmethod
    def _optimize_crystal(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize crystal structure."""
        return SymmetryReducer.reduce_crystal(structure, tolerance)

    @staticmethod
    def _optimize_molecule(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize molecular structure."""
        return SymmetryReducer.reduce_molecule(structure, tolerance)
