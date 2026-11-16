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
