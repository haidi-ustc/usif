"""spglib-based symmetry analysis and lossless asymmetric-unit storage.

* :func:`analyze` reports the space group of a periodic structure.
* :func:`reduce` returns a :class:`SymmetricForm` when it is lossless.
* :func:`expand` rebuilds every atom of a :class:`SymmetricForm`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from usif.errors import ValidationError
from usif.model.structure import Structure
from usif.symmetry.expand import SymmetricForm, expand
from usif.symmetry.reduce import LOSSLESS_TOLERANCE, reduce
from usif.symmetry.spacegroup import analyze_crystal

__all__ = ["LOSSLESS_TOLERANCE", "SpacegroupInfo", "SymmetricForm", "analyze", "expand", "reduce"]


@dataclass(frozen=True)
class SpacegroupInfo:
    number: int
    symbol: str
    hall_number: int
    wyckoffs: tuple[str, ...]
    equivalent_atoms: tuple[int, ...]


def analyze(structure: Structure, symprec: float = 1e-3) -> SpacegroupInfo:
    """Space group of a 3D-periodic structure as found by spglib."""
    if structure.cell is None or structure.pbc != (True, True, True):
        raise ValidationError("space-group analysis needs a 3D-periodic structure")
    result = analyze_crystal(
        structure.cell.matrix,
        np.mod(structure.frac_positions, 1.0),
        structure.numbers,
        symprec=symprec,
    )
    if result is None:
        raise ValidationError(f"spglib could not determine the symmetry at symprec={symprec}")
    return SpacegroupInfo(
        number=result.spacegroup,
        symbol=result.international,
        hall_number=result.hall_number,
        wyckoffs=result.wyckoffs,
        equivalent_atoms=tuple(int(i) for i in result.equivalent_atoms),
    )
