"""Periodic cell: a 3x3 lattice matrix plus periodic boundary flags."""

from __future__ import annotations

from functools import cached_property
from typing import Any, Iterable, Tuple

import numpy as np

from usif.errors import ValidationError

__all__ = ["Cell"]

Pbc = Tuple[bool, bool, bool]

#: Cells with |det| below this (Å^3) are rejected as degenerate.
MIN_CELL_VOLUME = 1e-8


def _readonly(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array


def _as_pbc(pbc: Any) -> Pbc:
    if isinstance(pbc, (bool, np.bool_)):
        flag = bool(pbc)
        return (flag, flag, flag)
    values = tuple(bool(p) for p in pbc)
    if len(values) != 3:
        raise ValidationError(f"pbc must have 3 entries, got {len(values)}")
    return (values[0], values[1], values[2])


class Cell:
    """Lattice vectors as matrix rows (Å) and per-axis periodicity.

    Instances are immutable; the matrix is a read-only float64 array.
    """

    def __init__(self, matrix: Any, pbc: Any = True) -> None:
        array = np.array(matrix, dtype=np.float64)
        if array.shape == (3,):
            array = np.diag(array)
        if array.shape != (3, 3):
            raise ValidationError(f"cell matrix must have shape (3, 3), got {array.shape}")
        if not np.all(np.isfinite(array)):
            raise ValidationError("cell matrix must be finite")
        if abs(float(np.linalg.det(array))) < MIN_CELL_VOLUME:
            raise ValidationError("cell matrix is degenerate (zero volume)")
        self._matrix = _readonly(array)
        self._pbc = _as_pbc(pbc)

    # -- data ---------------------------------------------------------------

    @property
    def matrix(self) -> np.ndarray:
        """Lattice vectors as rows, shape (3, 3), Å (read-only)."""
        return self._matrix

    @property
    def pbc(self) -> Pbc:
        return self._pbc

    @property
    def is_periodic(self) -> bool:
        return any(self._pbc)

    # -- derived ------------------------------------------------------------

    @cached_property
    def volume(self) -> float:
        return abs(float(np.linalg.det(self._matrix)))

    @cached_property
    def lengths(self) -> np.ndarray:
        return _readonly(np.linalg.norm(self._matrix, axis=1))

    @cached_property
    def angles(self) -> np.ndarray:
        """(alpha, beta, gamma) in degrees."""
        a, b, c = self._matrix
        la, lb, lc = self.lengths

        def angle(u: np.ndarray, v: np.ndarray, nu: float, nv: float) -> float:
            cosine = float(np.clip(np.dot(u, v) / (nu * nv), -1.0, 1.0))
            return float(np.degrees(np.arccos(cosine)))

        return _readonly(np.array([angle(b, c, lb, lc), angle(a, c, la, lc), angle(a, b, la, lb)]))

    @cached_property
    def inverse(self) -> np.ndarray:
        return _readonly(np.linalg.inv(self._matrix))

    def to_fractional(self, positions: Any) -> np.ndarray:
        """Cartesian (N, 3) -> fractional (N, 3)."""
        return np.asarray(positions, dtype=np.float64) @ self.inverse

    def to_cartesian(self, fractional: Any) -> np.ndarray:
        """Fractional (N, 3) -> Cartesian (N, 3)."""
        return np.asarray(fractional, dtype=np.float64) @ self._matrix

    # -- protocol -----------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Cell):
            return NotImplemented
        return self._pbc == other._pbc and np.array_equal(self._matrix, other._matrix)

    def __hash__(self) -> int:
        return hash((self._matrix.tobytes(), self._pbc))

    def allclose(self, other: "Cell", atol: float = 1e-8) -> bool:
        return self._pbc == other._pbc and np.allclose(
            self._matrix, other._matrix, atol=atol, rtol=0
        )

    def __repr__(self) -> str:
        a, b, c = (f"{x:.4f}" for x in self.lengths)
        al, be, ga = (f"{x:.2f}" for x in self.angles)
        return f"Cell(a={a}, b={b}, c={c}, alpha={al}, beta={be}, gamma={ga}, pbc={self._pbc})"

    @classmethod
    def cubic(cls, a: float, pbc: Iterable[bool] | bool = True) -> "Cell":
        return cls(np.eye(3) * float(a), pbc)
