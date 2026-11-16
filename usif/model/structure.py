"""The USIF structure model: atoms as arrays, an optional cell, typed properties."""

from __future__ import annotations

from functools import cached_property
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np

from usif.elements import atomic_number, element_symbol
from usif.errors import ValidationError
from usif.formula import element_counts, formula_from_counts
from usif.model.cell import Cell
from usif.model.properties import DEFAULT_SCHEMA, PropertyMap, Schema

__all__ = ["Structure"]

MAX_ATOMIC_NUMBER = 118


def _readonly(array: np.ndarray) -> np.ndarray:
    array.flags.writeable = False
    return array


def _as_numbers(numbers: Any) -> np.ndarray:
    values = list(numbers) if not isinstance(numbers, np.ndarray) else numbers
    if len(values) and any(isinstance(v, str) for v in values):
        values = [atomic_number(v) if isinstance(v, str) else v for v in values]
    array = np.asarray(values)
    if array.ndim != 1:
        raise ValidationError(f"numbers must be one-dimensional, got shape {array.shape}")
    if array.size == 0:
        raise ValidationError("a structure needs at least one atom")
    if array.dtype.kind not in "iu":
        if array.dtype.kind == "f" and np.all(np.mod(array, 1) == 0):
            array = array.astype(np.int64)
        else:
            raise ValidationError("numbers must be integer atomic numbers or element symbols")
    if array.min() < 1 or array.max() > MAX_ATOMIC_NUMBER:
        raise ValidationError(f"atomic numbers must be in 1..{MAX_ATOMIC_NUMBER}")
    return _readonly(array.astype(np.uint8))


def _as_positions(positions: Any, count: int) -> np.ndarray:
    try:
        array = np.array(positions, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"positions must be numeric: {exc}") from exc
    if array.shape != (count, 3):
        raise ValidationError(f"positions must have shape ({count}, 3), got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValidationError("positions must be finite")
    return _readonly(array)


def _as_cell(cell: Any, pbc: Any) -> Optional[Cell]:
    if cell is None:
        if pbc is not None and any(np.atleast_1d(pbc)):
            raise ValidationError("periodic boundary conditions need a cell")
        return None
    if isinstance(cell, Cell):
        return cell if pbc is None else Cell(cell.matrix, pbc)
    return Cell(cell, True if pbc is None else pbc)


class Structure:
    """A molecule or periodic structure.

    Parameters
    ----------
    numbers:
        Atomic numbers or element symbols, length N.
    positions:
        Cartesian coordinates in Å, shape (N, 3).
    cell:
        A :class:`Cell`, a 3x3 matrix (rows are lattice vectors) or ``None``
        for a molecule.
    pbc:
        Periodic boundary flags when ``cell`` is a matrix (default all True).
    arrays:
        Per-atom properties ``{name: array with leading dimension N}``.
    properties:
        Structure-level properties ``{name: scalar | array | JSON value}``.
    schema:
        Property specs used for validation and default units.

    Geometry (numbers, positions, cell) is immutable; use :meth:`replace` to
    derive a modified structure. ``arrays`` and ``properties`` are mutable
    :class:`~usif.model.properties.PropertyMap` objects validated on write.
    """

    def __init__(
        self,
        numbers: Any,
        positions: Any,
        cell: Any = None,
        *,
        pbc: Any = None,
        arrays: Optional[Mapping[str, Any]] = None,
        properties: Optional[Mapping[str, Any]] = None,
        schema: Schema = DEFAULT_SCHEMA,
    ) -> None:
        self._numbers = _as_numbers(numbers)
        self._positions = _as_positions(positions, len(self._numbers))
        self._cell = _as_cell(cell, pbc)
        self._schema = schema
        self.arrays = PropertyMap(schema.atom, len(self._numbers))
        self.properties = PropertyMap(schema.structure)
        self.arrays.update_from(arrays)
        self.properties.update_from(properties)

    @classmethod
    def from_fractional(
        cls,
        numbers: Any,
        fractional: Any,
        cell: Any,
        **kwargs: Any,
    ) -> "Structure":
        """Build a periodic structure from fractional coordinates."""
        cell_obj = _as_cell(cell, kwargs.pop("pbc", None))
        if cell_obj is None:
            raise ValidationError("fractional coordinates need a cell")
        return cls(numbers, cell_obj.to_cartesian(fractional), cell_obj, **kwargs)

    # -- geometry -----------------------------------------------------------

    @property
    def numbers(self) -> np.ndarray:
        """Atomic numbers, uint8, shape (N,), read-only."""
        return self._numbers

    @property
    def positions(self) -> np.ndarray:
        """Cartesian positions in Å, float64, shape (N, 3), read-only."""
        return self._positions

    @property
    def cell(self) -> Optional[Cell]:
        return self._cell

    @property
    def schema(self) -> Schema:
        return self._schema

    @property
    def natoms(self) -> int:
        return int(self._numbers.shape[0])

    def __len__(self) -> int:
        return self.natoms

    @property
    def is_periodic(self) -> bool:
        return self._cell is not None and self._cell.is_periodic

    @property
    def pbc(self) -> tuple[bool, bool, bool]:
        return self._cell.pbc if self._cell is not None else (False, False, False)

    @cached_property
    def frac_positions(self) -> np.ndarray:
        if self._cell is None:
            raise ValidationError("a structure without a cell has no fractional coordinates")
        return _readonly(self._cell.to_fractional(self._positions))

    @property
    def volume(self) -> Optional[float]:
        return self._cell.volume if self._cell is not None else None

    @cached_property
    def symbols(self) -> list[str]:
        return [element_symbol(int(z)) for z in self._numbers]

    @cached_property
    def element_counts(self) -> Dict[str, int]:
        return element_counts(self._numbers)

    @cached_property
    def formula(self) -> str:
        """Unreduced formula, e.g. ``"Na4Cl4"``."""
        return formula_from_counts(self.element_counts, reduce=False)

    @cached_property
    def reduced_formula(self) -> str:
        """Reduced formula, e.g. ``"NaCl"``."""
        return formula_from_counts(self.element_counts)

    @cached_property
    def chemical_system(self) -> str:
        """Sorted element set, e.g. ``"Cl-Na"``."""
        return "-".join(sorted(self.element_counts))

    # -- derivation ---------------------------------------------------------

    def copy(self) -> "Structure":
        return self.replace()

    def replace(
        self,
        *,
        numbers: Any = None,
        positions: Any = None,
        cell: Any = ...,
        pbc: Any = None,
        keep_properties: bool = True,
    ) -> "Structure":
        """Return a new structure with some geometry replaced.

        Per-atom arrays are kept only when the atom count is unchanged.
        ``cell=None`` removes the cell; omit it to keep the current one.
        """
        new = Structure.__new__(Structure)
        new._numbers = self._numbers if numbers is None else _as_numbers(numbers)
        count = len(new._numbers)
        new._positions = self._positions if positions is None else _as_positions(positions, count)
        if positions is None and count != self.natoms:
            raise ValidationError("changing the atom count needs new positions")
        if cell is ...:
            new._cell = self._cell if pbc is None else _as_cell(self._cell_matrix(), pbc)
        else:
            new._cell = _as_cell(cell, pbc)
        new._schema = self._schema
        if keep_properties and count == self.natoms:
            new.arrays = self.arrays.copy()
        else:
            new.arrays = PropertyMap(self._schema.atom, count)
        new.properties = (
            self.properties.copy() if keep_properties else PropertyMap(self._schema.structure)
        )
        return new

    def _cell_matrix(self) -> Optional[np.ndarray]:
        return None if self._cell is None else self._cell.matrix

    def permute(self, order: Sequence[int]) -> "Structure":
        """Return the structure with atoms reordered by ``order`` (a permutation)."""
        index = np.asarray(order, dtype=np.int64)
        if index.shape != (self.natoms,) or not np.array_equal(
            np.sort(index), np.arange(self.natoms)
        ):
            raise ValidationError("order must be a permutation of range(natoms)")
        new = self.replace(numbers=self._numbers[index], positions=self._positions[index])
        new.arrays = self.arrays.subset(index)
        return new

    # -- comparison ---------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Structure):
            return NotImplemented
        return (
            np.array_equal(self._numbers, other._numbers)
            and np.array_equal(self._positions, other._positions)
            and self._cell == other._cell
            and self.arrays == other.arrays
            and self.properties == other.properties
        )

    __hash__ = None  # type: ignore[assignment]

    def allclose(self, other: "Structure", atol: float = 1e-8) -> bool:
        """Equal up to ``atol`` in positions, cell and floating-point properties."""
        if not np.array_equal(self._numbers, other._numbers):
            return False
        if (self._cell is None) != (other._cell is None):
            return False
        if self._cell is not None and other._cell is not None:
            if not self._cell.allclose(other._cell, atol):
                return False
        if not np.allclose(self._positions, other._positions, atol=atol, rtol=0):
            return False
        return self.arrays.allclose(other.arrays, atol) and self.properties.allclose(
            other.properties, atol
        )

    def __repr__(self) -> str:
        kind = "periodic" if self.is_periodic else "molecule"
        extras = ""
        if len(self.arrays):
            extras += f", arrays={list(self.arrays)}"
        if len(self.properties):
            extras += f", properties={list(self.properties)}"
        return f"Structure({self.formula}, natoms={self.natoms}, {kind}{extras})"
