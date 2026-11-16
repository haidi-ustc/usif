"""Chemical formula helpers owned by the core (no external structure library).

:func:`reduced_formula` reproduces the reduced-formula convention USIF has
always indexed and queried (elements ordered by Pauling electronegativity,
polyanion grouping, and the special peroxide/diatomic names), so formulas are
identical no matter which adapter produced a structure.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Mapping, Tuple

import numpy as np

from usif.elements import ELECTRONEGATIVITY, element_symbol

_SPECIAL_FORMULAS = {
    "LiO": "Li2O2",
    "NaO": "Na2O2",
    "KO": "K2O2",
    "HO": "H2O2",
    "CsO": "Cs2O2",
    "RbO": "Rb2O2",
    "O": "O2",
    "N": "N2",
    "F": "F2",
    "Cl": "Cl2",
    "H": "H2",
}

#: Electronegativity gap below which the two most electronegative elements are
#: grouped as a polyanion, e.g. Li4P4O16 -> "LiPO4"... and Ca3(PO4)2.
_POLYANION_GAP = 1.65


def _electronegativity(symbol: str) -> float:
    value = ELECTRONEGATIVITY.get(symbol)
    return math.nan if value is None else value


def _sort_key(symbol: str):
    x = _electronegativity(symbol)
    return (math.inf if math.isnan(x) else x, symbol)


def _reduce(amounts: Dict[str, int]) -> Tuple[str, int]:
    symbols: List[str] = sorted((s for s in amounts if amounts[s] != 0), key=_sort_key)
    factor = abs(math.gcd(*amounts.values())) if amounts else 1

    polyanion = ""
    if (
        len(symbols) >= 3
        and _electronegativity(symbols[-1]) - _electronegativity(symbols[-2]) < _POLYANION_GAP
    ):
        poly_form, poly_factor = _reduce({s: amounts[s] // factor for s in symbols[-2:]})
        if poly_factor != 1:
            polyanion = f"({poly_form}){poly_factor}"
            symbols = symbols[:-2]

    parts = []
    for symbol in symbols:
        count = amounts[symbol] // factor
        parts.append(symbol if count == 1 else f"{symbol}{count}")
    return "".join(parts) + polyanion, factor


def element_counts(atomic_numbers: Iterable[int]) -> Dict[str, int]:
    """Return ``{symbol: count}`` (in order of atomic number) for a sequence of atomic numbers."""
    if not isinstance(atomic_numbers, np.ndarray):
        atomic_numbers = np.fromiter(atomic_numbers, dtype=np.int64)
    numbers = atomic_numbers
    if numbers.size == 0:
        return {}
    counts = np.bincount(numbers.astype(np.int64).ravel())
    present = np.flatnonzero(counts)
    return {element_symbol(int(z)): int(counts[z]) for z in present}


def formula_from_counts(counts: Mapping[str, int], *, reduce: bool = True) -> str:
    """Formula from ``{symbol: count}``; reduced (``"NaCl"``) or full (``"Na4Cl4"``)."""
    if not counts:
        return ""
    if reduce:
        formula, _ = _reduce(dict(counts))
        return _SPECIAL_FORMULAS.get(formula, formula)
    parts = []
    for symbol in sorted(counts, key=_sort_key):
        count = counts[symbol]
        parts.append(symbol if count == 1 else f"{symbol}{count}")
    return "".join(parts)


def reduced_formula(atomic_numbers: Iterable[int]) -> str:
    """Return the reduced formula of a set of atoms, e.g. ``[11, 17, 11, 17]`` -> ``"NaCl"``."""
    return formula_from_counts(element_counts(atomic_numbers))


def full_formula(atomic_numbers: Iterable[int]) -> str:
    """Return the unreduced formula, e.g. ``[11, 17, 11, 17]`` -> ``"Na2Cl2"``.

    Elements are ordered as in :func:`reduced_formula` (by electronegativity).
    """
    return formula_from_counts(element_counts(atomic_numbers), reduce=False)


def chemical_system(atomic_numbers: Iterable[int]) -> str:
    """Return the alphabetically sorted, dash-joined element set, e.g. ``"Cl-Na"``."""
    return "-".join(sorted(element_counts(atomic_numbers)))
