"""Symmetric (asymmetric-unit) form of a periodic structure and its expansion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from usif.errors import FormatError, ValidationError
from usif.symmetry.spacegroup import expand_orbit, setting_operations, spacegroup_of_hall

__all__ = ["SymmetricForm", "canonical_order", "expand"]

#: Rounding (fractional) applied before sorting expanded atoms canonically.
CANONICAL_ROUNDING = 1e-8


def _frozen(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array


@dataclass(frozen=True, eq=False)
class SymmetricForm:
    """Asymmetric unit of a periodic structure in its stored cell.

    ``transformation`` (P) and ``origin_shift`` (p) map stored-cell fractional
    coordinates to the standard setting of ``hall_number``: ``x_std = P x + p``.
    ``order`` (optional) restores the original atom order: atom ``i`` of the
    structure is atom ``order[i]`` of the canonical expansion.
    """

    hall_number: int
    transformation: np.ndarray
    origin_shift: np.ndarray
    numbers: np.ndarray
    multiplicities: np.ndarray
    positions: np.ndarray  # fractional, shape (R, 3)
    order: Optional[np.ndarray] = field(default=None)

    def __post_init__(self) -> None:
        if not 1 <= int(self.hall_number) <= 530:
            raise ValidationError(f"Hall number must be in 1..530, got {self.hall_number}")
        P = np.array(self.transformation, dtype=np.float64).reshape(3, 3)
        p = np.array(self.origin_shift, dtype=np.float64).reshape(3)
        if not (np.all(np.isfinite(P)) and np.all(np.isfinite(p))):
            raise ValidationError("symmetry setting must be finite")
        if abs(float(np.linalg.det(P))) < 1e-9:
            raise ValidationError("symmetry setting transformation is singular")
        numbers = np.array(self.numbers, dtype=np.uint8).reshape(-1)
        mult = np.array(self.multiplicities, dtype=np.int64).reshape(-1)
        positions = np.array(self.positions, dtype=np.float64).reshape(-1, 3)
        if not (len(numbers) == len(mult) == len(positions)) or len(numbers) == 0:
            raise ValidationError("representative arrays must be non-empty and equally long")
        if np.any(mult < 1):
            raise ValidationError("multiplicities must be positive")
        if not np.all(np.isfinite(positions)):
            raise ValidationError("representative positions must be finite")
        object.__setattr__(self, "hall_number", int(self.hall_number))
        object.__setattr__(self, "transformation", _frozen(P))
        object.__setattr__(self, "origin_shift", _frozen(p))
        object.__setattr__(self, "numbers", _frozen(numbers))
        object.__setattr__(self, "multiplicities", _frozen(mult))
        object.__setattr__(self, "positions", _frozen(positions))
        if self.order is not None:
            order = np.array(self.order, dtype=np.int64).reshape(-1)
            if order.shape[0] != self.natoms or not np.array_equal(
                np.sort(order), np.arange(self.natoms)
            ):
                raise ValidationError("order must be a permutation of the expanded atoms")
            object.__setattr__(self, "order", _frozen(order))

    @property
    def natoms(self) -> int:
        return int(self.multiplicities.sum())

    @property
    def spacegroup(self) -> int:
        return spacegroup_of_hall(self.hall_number)

    def operations(self) -> Tuple[np.ndarray, np.ndarray]:
        return setting_operations(self.hall_number, self.transformation, self.origin_shift)


def canonical_order(numbers: np.ndarray, fractional: np.ndarray) -> np.ndarray:
    """Indices sorting atoms by Z, then by wrapped, rounded fractional coordinates."""
    wrapped = np.mod(np.round(np.mod(fractional, 1.0) / CANONICAL_ROUNDING), 1 / CANONICAL_ROUNDING)
    return np.lexsort((wrapped[:, 2], wrapped[:, 1], wrapped[:, 0], numbers))


def expand(form: SymmetricForm) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(numbers, fractional_positions)`` of every atom.

    Atoms come in the canonical order (:func:`canonical_order`) unless the
    form carries an ``order``, which is then applied.
    """
    rotations, translations = form.operations()
    numbers = []
    images = []
    for z, mult, rep in zip(form.numbers, form.multiplicities, form.positions):
        orbit = expand_orbit(rep, rotations, translations, int(mult))
        if len(orbit) != int(mult):
            raise FormatError(
                f"representative Z={int(z)} expands to {len(orbit)} atoms, "
                f"multiplicity says {int(mult)}"
            )
        images.append(orbit)
        numbers.append(np.full(len(orbit), z, dtype=np.uint8))
    all_numbers = np.concatenate(numbers)
    all_frac = np.concatenate(images)
    canonical = canonical_order(all_numbers, all_frac)
    all_numbers, all_frac = all_numbers[canonical], all_frac[canonical]
    if form.order is not None:
        all_numbers, all_frac = all_numbers[form.order], all_frac[form.order]
    return all_numbers, all_frac
