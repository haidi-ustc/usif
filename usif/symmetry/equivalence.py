"""Symmetry coordinate expansion and equivalence checks."""

import logging

import numpy as np

from usif.constants import SymmetryConstants

logger = logging.getLogger(__name__)

POINT_GROUP_ALIASES = {
    "C1": "1",
    "Ci": "-1",
    "Cs": "m",
    "C2": "2",
    "C2h": "2/m",
    "C2v": "mm2",
    "D2": "222",
    "D2h": "mmm",
}

class SymmetryOperations:
    """Coordinate expansion and equivalence checks for symmetry-generated sites."""

    @staticmethod
    def crystal_sites_match(pmg_structure, spacegroup_number, wyckoff_sites):
        try:
            from pymatgen.symmetry.groups import SpaceGroup

            symmetry_ops = SpaceGroup.from_int_number(spacegroup_number).symmetry_ops
        except Exception:
            return False

        expanded = []
        for site in wyckoff_sites:
            for coord in SymmetryOperations.expand_fractional_orbit(
                site.coords, symmetry_ops, site.multiplicity
            ):
                expanded.append((site.atomic_number, coord))

        original = [
            (site.specie.Z, tuple(float(x % 1.0) for x in site.frac_coords))
            for site in pmg_structure
        ]
        return SymmetryOperations.site_sets_equal(original, expanded, periodic=True)

    @staticmethod
    def molecular_sites_match(pmg_molecule, point_group, point_group_sites):
        try:
            from pymatgen.symmetry.groups import PointGroup

            pg_symbol = POINT_GROUP_ALIASES.get(point_group, point_group)
            symmetry_ops = PointGroup(pg_symbol).symmetry_ops
        except Exception:
            return False

        expanded = []
        for site in point_group_sites:
            for coord in SymmetryOperations.expand_cartesian_orbit(
                site.coords, symmetry_ops, site.multiplicity
            ):
                expanded.append((site.atomic_number, coord))

        original = [
            (site.specie.Z, tuple(float(x) for x in site.coords))
            for site in pmg_molecule
        ]
        return SymmetryOperations.site_sets_equal(original, expanded, periodic=False)

    @staticmethod
    def site_sets_equal(left, right, periodic):
        if len(left) != len(right):
            return False

        unmatched = list(right)
        for atomic_number, coord in left:
            match_idx = None
            for idx, (candidate_number, candidate_coord) in enumerate(unmatched):
                if atomic_number != candidate_number:
                    continue
                if SymmetryOperations.coords_equal(coord, candidate_coord, periodic):
                    match_idx = idx
                    break
            if match_idx is None:
                return False
            unmatched.pop(match_idx)
        return True

    @staticmethod
    def coords_equal(left, right, periodic):
        diff = np.array(left, dtype=float) - np.array(right, dtype=float)
        if periodic:
            diff -= np.round(diff)
        return np.linalg.norm(diff) < SymmetryConstants.COORDINATE_TOLERANCE

    @staticmethod
    def expand_fractional_orbit(coords, symmetry_ops, multiplicity):
        expanded = []
        for op in symmetry_ops:
            transformed = tuple(float(x % 1.0) for x in op.operate(coords))
            if not SymmetryOperations.contains_coord(
                expanded, transformed, periodic=True
            ):
                expanded.append(transformed)
            if len(expanded) == multiplicity:
                break

        if len(expanded) != multiplicity:
            logger.debug(
                "Generated %d equivalent fractional sites, expected %d",
                len(expanded),
                multiplicity,
            )

        return expanded or [coords] * multiplicity

    @staticmethod
    def expand_cartesian_orbit(coords, symmetry_ops, multiplicity):
        expanded = []
        for op in symmetry_ops:
            transformed = tuple(float(x) for x in op.operate(coords))
            if not SymmetryOperations.contains_coord(
                expanded, transformed, periodic=False
            ):
                expanded.append(transformed)
            if len(expanded) == multiplicity:
                break

        if len(expanded) != multiplicity:
            logger.debug(
                "Generated %d equivalent Cartesian sites, expected %d",
                len(expanded),
                multiplicity,
            )

        return expanded or [coords] * multiplicity

    @staticmethod
    def contains_coord(existing, candidate, periodic):
        tol = SymmetryConstants.COORDINATE_TOLERANCE
        candidate_arr = np.array(candidate, dtype=float)
        for coord in existing:
            diff = candidate_arr - np.array(coord, dtype=float)
            if periodic:
                diff -= np.round(diff)
            if np.linalg.norm(diff) < tol:
                return True
        return False


