"""Symmetry: spglib-based reduction, setting-aware expansion, and policies."""

from usif.symmetry.policies import SymmetryPolicy, apply_symmetry_policy

__all__ = [
    "SymmetryPolicy",
    "SymmetryReducer",
    "apply_symmetry_policy",
    "expand_structure",
]


def __getattr__(name: str):
    """Lazily import modules that pull in spglib."""
    if name == "SymmetryReducer":
        from usif.symmetry.reduce import SymmetryReducer

        return SymmetryReducer
    if name == "expand_structure":
        from usif.symmetry.expand import expand_structure

        return expand_structure
    raise AttributeError(f"module 'usif.symmetry' has no attribute {name!r}")
