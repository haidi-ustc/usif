#!/usr/bin/env python3
"""USIF package and release version metadata.

The packaging version and dated release record are defined in ``pyproject.toml``.
When the project is imported from a source checkout, this module reads that file
so release metadata has one editable source.  When imported from an installed
wheel where ``pyproject.toml`` is not available, it falls back to the static
values baked into this module by the release process.
"""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Any, Dict

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback when tomli is installed
    import tomli as tomllib  # type: ignore[no-redef]

# Binary format version (integer, incremented only for .usif record format changes).
FORMAT_VERSION = 5

_FALLBACK_VERSION = "6.0.0"
_FALLBACK_RELEASE_DATE = "2026-06-05"
_FALLBACK_RELEASE_SEQUENCE = 1
_FALLBACK_RELEASE_RECORD = "20260605.001"
_FALLBACK_RELEASE_ID = "usif-20260605-001"


def _find_source_pyproject() -> Path | None:
    """Return the nearest source-tree pyproject.toml, if available."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "pyproject.toml"
        if candidate.exists():
            return candidate
    return None


def _read_source_release_metadata() -> Dict[str, Any]:
    """Read version metadata from pyproject.toml in a source checkout."""
    pyproject = _find_source_pyproject()
    if pyproject is None:
        return {}
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project", {})
    release = data.get("tool", {}).get("usif", {}).get("release", {})
    return {
        "version": project.get("version"),
        "release_date": release.get("date"),
        "release_sequence": release.get("sequence"),
        "release_record": release.get("record"),
        "release_id": release.get("id"),
    }


def _installed_version() -> str | None:
    """Return installed package metadata version when available."""
    try:
        return metadata.version("usif")
    except metadata.PackageNotFoundError:
        return None


_source = _read_source_release_metadata()

# Prefer source pyproject.toml for editable/source-tree imports.  Installed
# wheels use package metadata for the public version and the baked release record
# constants below for non-packaging metadata.
__version__ = str(_source.get("version") or _installed_version() or _FALLBACK_VERSION)
RELEASE_DATE = str(_source.get("release_date") or _FALLBACK_RELEASE_DATE)
RELEASE_SEQUENCE = int(_source.get("release_sequence") or _FALLBACK_RELEASE_SEQUENCE)
RELEASE_RECORD = str(_source.get("release_record") or _FALLBACK_RELEASE_RECORD)
RELEASE_ID = str(_source.get("release_id") or _FALLBACK_RELEASE_ID)

VERSION_INFO = tuple(int(part) for part in __version__.split(".")[:3])
VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH = VERSION_INFO

__all__ = [
    "__version__",
    "FORMAT_VERSION",
    "VERSION_INFO",
    "VERSION_MAJOR",
    "VERSION_MINOR",
    "VERSION_PATCH",
    "RELEASE_DATE",
    "RELEASE_SEQUENCE",
    "RELEASE_RECORD",
    "RELEASE_ID",
]
