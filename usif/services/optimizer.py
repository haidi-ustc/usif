"""Structure optimization services."""

from __future__ import annotations

import logging

from usif.constants import SymmetryConstants
from usif.structures.structure import USIFStructure

logger = logging.getLogger(__name__)


class USIFOptimizer:
    """Optimize USIF structures for compact symmetry-aware storage."""

    @staticmethod
    def optimize_structure(
        structure: USIFStructure,
        tolerance: float = SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE,
    ) -> USIFStructure:
        """Return an optimized structure using symmetry reduction when possible."""
        if structure.is_crystal():
            return USIFOptimizer._optimize_crystal(structure, tolerance)
        return USIFOptimizer._optimize_molecule(structure, tolerance)

    @staticmethod
    def _optimize_crystal(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Reduce a crystal to symmetric storage when that is exact *and* smaller."""
        from usif.encoder import USIF
        from usif.symmetry.reduce import SymmetryReducer

        reduced = SymmetryReducer.reduce_crystal(structure, tolerance)
        if reduced is structure:
            return structure
        codec = USIF()
        if len(codec.encode(reduced)) >= len(codec.encode(structure)):
            return structure
        return reduced

    @staticmethod
    def _optimize_molecule(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize a molecular structure."""
        from usif.symmetry.reduce import SymmetryReducer

        return SymmetryReducer.reduce_molecule(structure, tolerance)


def optimize_structure(
    structure: USIFStructure,
    tolerance: float = SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE,
) -> USIFStructure:
    """Functional entry point for structure optimization."""
    return USIFOptimizer.optimize_structure(structure, tolerance)
