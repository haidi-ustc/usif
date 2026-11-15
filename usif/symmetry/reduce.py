"""Lossless symmetry reduction of full-atomic crystals (spglib backed)."""

from __future__ import annotations

import copy
import logging
from typing import Dict, List, Optional, Sequence

import numpy as np

from usif.constants import StorageMode, StructureType, SymmetryConstants
from usif.properties.atomic import AtomicProperties
from usif.structures.metadata import SYMMETRY_METADATA_KEY
from usif.structures.sites import WyckoffSite
from usif.structures.structure import USIFStructure
from usif.symmetry.spacegroup import (
    analyze_crystal,
    expand_orbit,
    setting_operations,
    xyz_tuple,
)

logger = logging.getLogger(__name__)

#: Above this many atoms the pairwise lossless check is skipped (kept full-atomic).
MAX_REDUCTION_ATOMS = 20_000


def has_atomic_data(properties: AtomicProperties) -> bool:
    """True when an atom carries any per-atom value that symmetry storage would lose."""
    return any(
        value is not None
        for value in (properties.force, properties.charge, properties.magmom, properties.velocity)
    ) or bool(properties.custom)


def structure_has_atomic_data(structure: USIFStructure) -> bool:
    return any(has_atomic_data(site.properties) for site in structure.atom_sites or [])


def _symprec_candidates(tolerance: float) -> List[float]:
    """Coarse to fine: a coarse tolerance can find a higher symmetry that is not
    exact, while a finer one may still find an exact lower symmetry."""
    values = [tolerance] + [v for v in (1e-3, 1e-5) if v < tolerance]
    return sorted(set(values), reverse=True)


def _as_stored(values: np.ndarray) -> np.ndarray:
    """Round to the float32 precision records store coordinates and lattices in."""
    return np.asarray(values, dtype=np.float32).astype(float)


def _sites_match(
    lattice: np.ndarray,
    numbers: Sequence[int],
    frac: np.ndarray,
    expanded: Dict[int, np.ndarray],
    tolerance: float,
) -> bool:
    """True when the expanded atoms equal the original atoms (as a set) within ``tolerance`` Å."""
    numbers_arr = np.asarray(numbers)
    for z, candidates in expanded.items():
        originals = frac[numbers_arr == z]
        if len(originals) != len(candidates):
            return False
        diff = originals[:, None, :] - candidates[None, :, :]
        diff -= np.round(diff)
        dist = np.linalg.norm(diff @ lattice, axis=2)
        # Each original must match a distinct candidate. Images are separated by
        # far more than the tolerance, so a nearest-neighbour check per row plus
        # a uniqueness check on the chosen columns is exact.
        nearest = dist.argmin(axis=1)
        if not np.all(dist[np.arange(len(originals)), nearest] <= tolerance):
            return False
        if len(set(nearest.tolist())) != len(originals):
            return False
    return set(expanded) == set(numbers_arr.tolist())


class SymmetryReducer:
    """Convert full-atomic crystals to symmetric storage when it is exact."""

    @staticmethod
    def reduce_crystal(
        structure: USIFStructure,
        tolerance: float = SymmetryConstants.DEFAULT_SPACEGROUP_TOLERANCE,
        *,
        lossless_tolerance: float = SymmetryConstants.LOSSLESS_TOLERANCE,
        require_gain: bool = True,
    ) -> USIFStructure:
        """Return a symmetric equivalent of ``structure`` or ``structure`` itself.

        The result is symmetric only if expanding it reproduces every atom of
        the input to within ``lossless_tolerance`` Angstrom after float32
        rounding, i.e. it never stores less information than full-atomic mode.
        Atom order is not preserved by symmetric storage. Structures with
        per-atom properties are never reduced here; callers decide via
        :class:`~usif.symmetry.policies.SymmetryPolicy` whether to drop them.
        With ``require_gain`` (default) a structure whose atoms are all
        symmetry-distinct is left full-atomic, since nothing would be saved.
        """
        if structure.storage_mode != StorageMode.FULL_ATOMIC or not structure.is_crystal():
            return structure
        sites = structure.atom_sites or []
        if not sites or len(sites) > MAX_REDUCTION_ATOMS:
            return structure
        if structure_has_atomic_data(structure):
            logger.debug("Structure has per-atom properties; keeping full atomic storage")
            return structure

        if structure.lattice_matrix is None:
            return structure
        lattice = _as_stored(structure.lattice_matrix)
        numbers = [site.atomic_number for site in sites]
        frac = np.mod(_as_stored(np.array([site.coords for site in sites], dtype=float)), 1.0)

        for symprec in _symprec_candidates(tolerance):
            candidate = SymmetryReducer._candidate(
                structure, lattice, numbers, frac, symprec, require_gain
            )
            if candidate is None:
                break  # finer tolerances cannot find more symmetry
            if SymmetryReducer._is_lossless(candidate, lattice, numbers, frac, lossless_tolerance):
                return candidate
        return structure

    @staticmethod
    def _candidate(
        structure: USIFStructure,
        lattice: np.ndarray,
        numbers: List[int],
        frac: np.ndarray,
        symprec: float,
        require_gain: bool = True,
    ) -> Optional[USIFStructure]:
        try:
            symmetry = analyze_crystal(lattice, frac, numbers, symprec=symprec)
        except Exception as exc:  # spglib raises on degenerate cells
            logger.debug("Symmetry analysis failed at symprec=%s: %s", symprec, exc)
            return None
        if symmetry is None:
            return None
        representatives: Dict[int, int] = {}
        for index, rep in enumerate(symmetry.equivalent_atoms):
            representatives.setdefault(int(rep), 0)
            representatives[int(rep)] += 1
        if require_gain and len(representatives) == len(numbers):
            return None  # no atom is generated by symmetry: nothing to gain

        wyckoff_sites = [
            WyckoffSite(numbers[rep], count, xyz_tuple(frac[rep]))
            for rep, count in representatives.items()
        ]
        # No symmetry metadata is attached: a format-6 symmetric record is
        # lossless by construction and fully describes its own setting.
        properties = copy.deepcopy(structure.structure_properties)
        properties.custom.pop(SYMMETRY_METADATA_KEY, None)
        return USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.array(structure.lattice_matrix, dtype=float),
            spacegroup=symmetry.spacegroup,
            hall_number=symmetry.hall_number,
            setting_transformation=symmetry.transformation,
            origin_shift=symmetry.origin_shift,
            wyckoff_sites=wyckoff_sites,
            structure_properties=properties,
            formula=structure.formula,
        )

    @staticmethod
    def _is_lossless(
        candidate: USIFStructure,
        lattice: np.ndarray,
        numbers: List[int],
        frac: np.ndarray,
        tolerance: float,
    ) -> bool:
        hall, P, p = candidate.symmetry_setting()
        rotations, translations = setting_operations(hall, P, p)
        expanded: Dict[int, List[np.ndarray]] = {}
        for site in candidate.wyckoff_sites or []:
            stored = _as_stored(np.array(site.coords, dtype=float))
            images = expand_orbit(stored, rotations, translations)
            if len(images) != site.multiplicity:
                return False
            expanded.setdefault(site.atomic_number, []).extend(images)
        return _sites_match(
            lattice,
            numbers,
            frac,
            {z: np.array(v) for z, v in expanded.items()},
            tolerance,
        )

    @staticmethod
    def reduce_molecule(structure: USIFStructure, tolerance: float = 0.0) -> USIFStructure:
        """Molecules are always stored full-atomic.

        Point-group storage needs a reliable molecular point-group analyzer
        and saves little space for molecules; format-5 point-group records
        remain readable through :func:`usif.symmetry.expand.expand_structure`.
        """
        return structure
