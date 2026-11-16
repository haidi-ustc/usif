"""Unit strings: spelling normalisation, and conversion for the built-in quantities.

Stored values are never converted: a unit is a label kept next to the value,
and :func:`normalize_unit` only canonicalises its spelling (``Å²``, ``Ang^2``
and ``angstrom^2`` all read ``Å^2``; ``µB``, ``muB`` and ``uB`` read ``μB``).

:func:`convert` is used where a value must leave USIF in a fixed unit system
(for example ASE expects eV, eV/Å and eV/Å^3). It knows the common units of
energy, force, pressure/stress, length, velocity, charge and magnetic moment;
constants are CODATA 2018.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

import numpy as np

from usif.errors import ValidationError

__all__ = ["EV_PER_ANG3_IN_GPA", "convert", "normalize_unit"]

# CODATA 2018 (e, N_A exact; the others to their published digits).
_HARTREE_EV = 27.211386245988
_RYDBERG_EV = 13.605693122994
_BOHR_ANG = 0.529177210903
_EV_PER_KJ_MOL = 1.0 / 96.48533212331002  # 1 eV = e * N_A / 1000 kJ/mol

#: 1 eV/Å^3 in GPa: e / (1e-30 m^3) / 1e9 = 160.2176634 (exact).
EV_PER_ANG3_IN_GPA = 160.2176634

# unit -> (quantity, factor to the quantity's base unit)
_UNITS: Dict[str, Tuple[str, float]] = {}


def _define(quantity: str, units: Dict[str, float]) -> None:
    for name, factor in units.items():
        _UNITS[name] = (quantity, factor)


_define(
    "energy (eV)",
    {
        "eV": 1.0,
        "meV": 1e-3,
        "Ha": _HARTREE_EV,
        "Hartree": _HARTREE_EV,
        "Ry": _RYDBERG_EV,
        "kJ/mol": _EV_PER_KJ_MOL,
        "kcal/mol": 4.184 * _EV_PER_KJ_MOL,
    },
)
_define(
    "force (eV/Å)",
    {
        "eV/Å": 1.0,
        "meV/Å": 1e-3,
        "Ha/Bohr": _HARTREE_EV / _BOHR_ANG,
        "Ry/Bohr": _RYDBERG_EV / _BOHR_ANG,
        "kcal/mol/Å": 4.184 * _EV_PER_KJ_MOL,
    },
)
_define(
    "pressure (GPa)",
    {
        "GPa": 1.0,
        "MPa": 1e-3,
        "Pa": 1e-9,
        "kbar": 0.1,
        "bar": 1e-4,
        "atm": 1.01325e-4,
        "eV/Å^3": EV_PER_ANG3_IN_GPA,
    },
)
_define("length (Å)", {"Å": 1.0, "nm": 10.0, "pm": 0.01, "Bohr": _BOHR_ANG})
_define("velocity (Å/fs)", {"Å/fs": 1.0, "Å/ps": 1e-3, "m/s": 1e-5, "km/s": 1e-2})
_define("charge (e)", {"e": 1.0})
_define("magnetic moment (μB)", {"μB": 1.0})

_SUPERSCRIPT_TRANSLATION = str.maketrans(
    {
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
        "⁺": "+",
        "⁻": "-",
    }
)
_SUBSCRIPT_TRANSLATION = str.maketrans(
    {
        "₀": "0",
        "₁": "1",
        "₂": "2",
        "₃": "3",
        "₄": "4",
        "₅": "5",
        "₆": "6",
        "₇": "7",
        "₈": "8",
        "₉": "9",
        "₊": "+",
        "₋": "-",
    }
)


def _replace_superscript_runs(text: str) -> str:
    """Convert Unicode superscript runs to caret exponents."""

    chars = set("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    result: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char not in chars:
            result.append(char)
            index += 1
            continue
        start = index
        while index < len(text) and text[index] in chars:
            index += 1
        exponent = text[start:index].translate(_SUPERSCRIPT_TRANSLATION)
        result.append("^" + exponent)
    return "".join(result)


_ANGSTROM_TOKEN = re.compile(r"(?i)(?<![A-Za-z])(?:angstroms?|ang)(?![A-Za-z])")
_BOHR_MAGNETON_TOKEN = re.compile(r"(?<![A-Za-z])(?:mu_B|muB|uB)(?![A-Za-z])")
_BOHR_TOKEN = re.compile(r"(?i)(?<![A-Za-z])bohr(?![A-Za-z])")


@lru_cache(maxsize=4096)
def normalize_unit(unit: Optional[str]) -> str:
    """Canonical spelling of ``unit`` (``""`` for no unit); the value is not converted."""
    if unit is None:
        return ""
    if not isinstance(unit, str):
        raise TypeError(f"unit must be a string or None, got {type(unit).__name__}")
    text = unit.strip()
    if not text:
        return ""
    # NFC composes "A" + combining ring and maps ANGSTROM SIGN to "Å";
    # the MICRO SIGN is a compatibility character, so map it to Greek mu.
    text = unicodedata.normalize("NFC", text).replace("\u00b5", "μ")
    text = text.translate(_SUBSCRIPT_TRANSLATION)
    text = _replace_superscript_runs(text)
    text = text.replace(" ** ", "^").replace("**", "^")
    text = re.sub(r"\s*\^\s*", "^", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s+", " ", text)
    text = _ANGSTROM_TOKEN.sub("Å", text)
    text = re.sub(r"(?i)micro", "μ", text)
    text = _BOHR_MAGNETON_TOKEN.sub("μB", text)
    return _BOHR_TOKEN.sub("Bohr", text)


def convert(value: Any, from_unit: Optional[str], to_unit: str) -> Any:
    """Convert ``value`` (a number or array) from ``from_unit`` to ``to_unit``.

    Raises :class:`ValidationError` for an unknown unit or units of different
    quantities. Equal spellings return ``value`` unchanged.
    """
    source, target = normalize_unit(from_unit), normalize_unit(to_unit)
    if source == target:
        return value
    if source not in _UNITS or target not in _UNITS:
        unknown = source if source not in _UNITS else target
        raise ValidationError(
            f"cannot convert {source or 'unitless'!r} to {target!r}: "
            f"unknown unit {unknown or 'unitless'!r}"
        )
    (kind_a, factor_a), (kind_b, factor_b) = _UNITS[source], _UNITS[target]
    if kind_a != kind_b:
        raise ValidationError(f"cannot convert {source!r} ({kind_a}) to {target!r} ({kind_b})")
    scale = factor_a / factor_b
    if isinstance(value, np.ndarray):
        return value * scale
    return float(value) * scale
