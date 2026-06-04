"""Backward-compatible symmetry import path.

Use :mod:`usif.symmetry` for new code.
"""

from usif.symmetry import POINT_GROUP_ALIASES, SymmetryOperations, SymmetryReducer

__all__ = ["POINT_GROUP_ALIASES", "SymmetryOperations", "SymmetryReducer"]
