"""Backward-compatible public container module.

The implementation now lives in :mod:`usif.storage.container` so storage internals
can evolve independently from the top-level public import path.
"""

from usif.storage.container import StructureContainer, USIFGroup

__all__ = ["StructureContainer", "USIFGroup"]
