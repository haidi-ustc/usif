"""Lazy optional dependencies for Materials Project integration."""

from __future__ import annotations


def require_monty():
    """Return monty JSON helpers, importing them only when needed."""
    try:
        from monty.serialization import dumpfn, loadfn
    except ImportError as e:
        raise ImportError(
            "monty is required for Materials Project JSON I/O. Install with: pip install monty"
        ) from e
    return dumpfn, loadfn


def require_mp_rester():
    """Return Materials Project client class, importing mp-api only for downloads."""
    try:
        from mp_api.client import MPRester
    except ImportError as e:
        raise ImportError(
            "mp-api is required for Materials Project downloads. Install with: pip install mp-api"
        ) from e
    return MPRester


def require_pymatgen_structure():
    """Return pymatgen Structure class, importing it only when conversion needs it."""
    try:
        from pymatgen.core import Structure
    except ImportError as e:
        raise ImportError(
            "pymatgen is required for converting Materials Project structures. "
            "Install with: pip install pymatgen"
        ) from e
    return Structure
