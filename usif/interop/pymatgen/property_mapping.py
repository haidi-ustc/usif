"""Shared pymatgen property mapping hooks.

The detailed mapping still lives in ``converter_core`` during this compatibility
refactor.  This module is the stable extension point for future extraction.
"""

ATOMIC_PROPERTY_KEYS = ("forces", "charges", "magmoms")
STRUCTURE_PROPERTY_KEYS = ("energy", "stress")
