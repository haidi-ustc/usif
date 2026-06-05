"""Symmetry analysis, equivalence, policies, and reduction helpers."""

from usif.symmetry.analysis import extract_point_group_sites, extract_wyckoff_sites
from usif.symmetry.equivalence import POINT_GROUP_ALIASES, SymmetryOperations
from usif.symmetry.metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
from usif.symmetry.policies import SymmetryPolicy

__all__ = [
    "POINT_GROUP_ALIASES",
    "SYMMETRY_METADATA_KEY",
    "SymmetryMetadata",
    "SymmetryOperations",
    "SymmetryPolicy",
    "SymmetryReducer",
    "extract_point_group_sites",
    "extract_wyckoff_sites",
]


def __getattr__(name: str):
    """Lazily import heavy symmetry services."""
    if name == "SymmetryReducer":
        from usif.symmetry.reduce import SymmetryReducer

        return SymmetryReducer
    raise AttributeError(f"module 'usif.symmetry' has no attribute {name!r}")
