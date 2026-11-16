"""Lossless reduction of a periodic structure to its asymmetric unit."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from usif.model.structure import Structure
from usif.symmetry.expand import SymmetricForm, canonical_order
from usif.symmetry.spacegroup import analyze_crystal, expand_orbit, setting_operations

__all__ = ["LOSSLESS_TOLERANCE", "MAX_REDUCTION_ATOMS", "SYMPREC_CANDIDATES", "reduce"]

logger = logging.getLogger(__name__)

#: Maximum Cartesian deviation (Å) of a re-expanded atom from the original.
LOSSLESS_TOLERANCE = 1e-5
#: spglib tolerances tried, coarsest first; the first lossless result wins.
SYMPREC_CANDIDATES = (1e-1, 1e-3, 1e-5)
#: Larger structures are not analysed (spglib cost).
MAX_REDUCTION_ATOMS = 100_000

_GRID = 1e-3  # fractional bucket size for matching expanded atoms to originals


def reduce(
    structure: Structure,
    *,
    tolerance: float = LOSSLESS_TOLERANCE,
    symprecs: Sequence[float] = SYMPREC_CANDIDATES,
) -> Optional[SymmetricForm]:
    """Return the asymmetric-unit form of ``structure`` or ``None``.

    A form is returned only if it reproduces every atom, in the original
    order and lattice image, within ``tolerance`` Å, and if symmetry
    actually generates atoms. Structures with per-atom arrays, without
    full 3D periodicity, or above :data:`MAX_REDUCTION_ATOMS` atoms are not
    reduced.
    """
    if structure.cell is None or structure.pbc != (True, True, True):
        return None
    if len(structure.arrays) or structure.natoms > MAX_REDUCTION_ATOMS:
        return None
    lattice = structure.cell.matrix
    numbers = structure.numbers
    frac = structure.frac_positions

    for symprec in symprecs:
        form = _candidate(lattice, numbers, frac, symprec, tolerance)
        if form is not None:
            return form
    return None


def _candidate(
    lattice: np.ndarray,
    numbers: np.ndarray,
    frac: np.ndarray,
    symprec: float,
    tolerance: float,
) -> Optional[SymmetricForm]:
    try:
        symmetry = analyze_crystal(lattice, np.mod(frac, 1.0), numbers, symprec=symprec)
    except Exception as exc:  # spglib raises on pathological cells
        logger.debug("spglib failed at symprec=%s: %s", symprec, exc)
        return None
    if symmetry is None:
        return None
    reps: Dict[int, int] = {}
    for rep in symmetry.equivalent_atoms:
        reps[int(rep)] = reps.get(int(rep), 0) + 1
    if len(reps) == len(numbers):
        return None  # symmetry generates nothing

    rep_index = np.fromiter(reps, dtype=np.int64)
    rep_frac = np.mod(frac[rep_index], 1.0)
    rotations, translations = setting_operations(
        symmetry.hall_number, symmetry.transformation, symmetry.origin_shift
    )
    expanded_numbers: List[np.ndarray] = []
    expanded_frac: List[np.ndarray] = []
    for index, position in zip(rep_index, rep_frac):
        orbit = expand_orbit(position, rotations, translations)
        if len(orbit) != reps[int(index)]:
            return None
        expanded_frac.append(orbit)
        expanded_numbers.append(np.full(len(orbit), numbers[index], dtype=np.uint8))
    all_numbers = np.concatenate(expanded_numbers)
    all_frac = np.concatenate(expanded_frac)
    canonical = canonical_order(all_numbers, all_frac)
    all_numbers, all_frac = all_numbers[canonical], all_frac[canonical]

    order = _match(lattice, numbers, frac, all_numbers, all_frac, tolerance)
    if order is None:
        return None
    identity = np.array_equal(order, np.arange(len(order)))
    return SymmetricForm(
        hall_number=symmetry.hall_number,
        transformation=symmetry.transformation,
        origin_shift=symmetry.origin_shift,
        numbers=numbers[rep_index],
        multiplicities=np.fromiter(reps.values(), dtype=np.int64),
        positions=rep_frac,
        order=None if identity else order,
    )


def _match(
    lattice: np.ndarray,
    numbers: np.ndarray,
    frac: np.ndarray,
    expanded_numbers: np.ndarray,
    expanded_frac: np.ndarray,
    tolerance: float,
) -> Optional[np.ndarray]:
    """``order`` with ``expanded[order[i]] == original[i]`` within ``tolerance``, or None.

    Matching is periodic (bucketed by wrapped fractional coordinates); the
    final check is non-periodic, so an original atom outside the cell does
    not match its in-cell image.
    """
    if len(expanded_numbers) != len(numbers):
        return None
    cells = int(round(1.0 / _GRID))
    buckets: Dict[Tuple[int, int, int, int], List[int]] = defaultdict(list)
    keys = np.floor(np.mod(expanded_frac, 1.0) * cells).astype(np.int64) % cells
    for j, (z, key) in enumerate(zip(expanded_numbers, keys)):
        buckets[(int(z), int(key[0]), int(key[1]), int(key[2]))].append(j)

    used = np.zeros(len(expanded_numbers), dtype=bool)
    order = np.empty(len(numbers), dtype=np.int64)
    original_keys = np.floor(np.mod(frac, 1.0) * cells).astype(np.int64) % cells
    offsets = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)]
    for i, (z, key) in enumerate(zip(numbers, original_keys)):
        best = -1
        best_distance = np.inf
        for da, db, dc in offsets:
            bucket = buckets.get(
                (
                    int(z),
                    int((key[0] + da) % cells),
                    int((key[1] + db) % cells),
                    int((key[2] + dc) % cells),
                )
            )
            if not bucket:
                continue
            for j in bucket:
                if used[j]:
                    continue
                delta = frac[i] - expanded_frac[j]
                delta -= np.round(delta)
                distance = float(np.linalg.norm(delta @ lattice))
                if distance < best_distance:
                    best, best_distance = j, distance
        if best < 0 or best_distance > tolerance:
            return None
        used[best] = True
        order[i] = best

    # Non-periodic check: the decoded atom must lie in the same lattice image.
    deviation = (frac - expanded_frac[order]) @ lattice
    if float(np.max(np.linalg.norm(deviation, axis=1))) > tolerance:
        return None
    return order
