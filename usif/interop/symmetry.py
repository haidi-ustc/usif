"""Shared symmetry helpers used by converters and optimizers."""

import logging
from collections import defaultdict

import numpy as np
from pymatgen.symmetry.analyzer import PointGroupAnalyzer, SpacegroupAnalyzer

from usif.constants import StorageMode, StructureType, SymmetryConstants
from usif.exceptions import ValidationError
from usif.structures.metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
from usif.structures.sites import PointGroupSite, WyckoffSite
from usif.structures.structure import USIFStructure

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


class SymmetryReducer:
    """Convert full atomic USIF structures to symmetric representations."""

    @staticmethod
    def reduce_crystal(structure: USIFStructure, tolerance: float) -> USIFStructure:
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure

        try:
            from usif.converter import StructureConverter

            pmg_structure = StructureConverter.to_pymatgen(structure)
            sga = SpacegroupAnalyzer(pmg_structure, symprec=tolerance)
            symmetrized = sga.get_symmetrized_structure()

            wyckoff_sites = []
            for equiv_sites in symmetrized.equivalent_sites:
                rep = equiv_sites[0]
                wyckoff_sites.append(
                    WyckoffSite(rep.specie.Z, len(equiv_sites), tuple(rep.frac_coords))
                )

            structure.structure_properties.custom[SYMMETRY_METADATA_KEY] = SymmetryMetadata(
                lossless=True,
                reconstruction_mode="spacegroup_expansion",
                symmetry_origin="pymatgen_spacegroup",
                source_coordinate_frame="fractional",
                tolerance=tolerance,
            ).as_dict()

            return USIFStructure(
                structure_type=StructureType.CRYSTAL,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=structure.lattice_matrix,
                spacegroup=sga.get_space_group_number(),
                wyckoff_sites=wyckoff_sites,
                structure_properties=structure.structure_properties,
                formula=structure.formula,
            )
        except (ValueError, RuntimeError) as e:
            logger.debug(
                "Crystal optimization failed due to symmetry analysis error: %s", e
            )
            return structure
        except ValidationError as e:
            logger.warning("Crystal optimization failed due to validation error: %s", e)
            return structure
        except Exception as e:
            logger.error(
                "Unexpected error during crystal optimization: %s", e, exc_info=True
            )
            return structure

    @staticmethod
    def reduce_molecule(structure: USIFStructure, tolerance: float) -> USIFStructure:
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure

        try:
            from usif.converter import StructureConverter

            pmg_molecule = StructureConverter.to_pymatgen(structure)
            pga = PointGroupAnalyzer(pmg_molecule)
            point_group = pga.sch_symbol

            atom_groups = defaultdict(list)
            for i, site in enumerate(pmg_molecule):
                atom_groups[site.specie.Z].append((i, np.array(site.coords)))

            point_group_sites = []
            used = set()
            for atomic_num, atoms in atom_groups.items():
                for idx, coords in atoms:
                    if idx in used:
                        continue

                    equiv_count = 1
                    used.add(idx)

                    for other_idx, other_coords in atoms:
                        if other_idx in used:
                            continue

                        min_dist = float("inf")
                        for sym_op in pga.get_symmetry_operations():
                            transformed = sym_op.operate(coords)
                            dist = np.linalg.norm(transformed - other_coords)
                            min_dist = min(min_dist, dist)

                        if min_dist < tolerance:
                            equiv_count += 1
                            used.add(other_idx)

                    point_group_sites.append(
                        PointGroupSite(atomic_num, equiv_count, tuple(coords))
                    )

            total_multiplicity = sum(s.multiplicity for s in point_group_sites)
            if total_multiplicity == len(pmg_molecule) and len(point_group_sites) < len(
                pmg_molecule
            ):
                structure.structure_properties.custom[SYMMETRY_METADATA_KEY] = SymmetryMetadata(
                    lossless=True,
                    reconstruction_mode="point_group_expansion",
                    symmetry_origin="pymatgen_point_group",
                    source_coordinate_frame="cartesian",
                    tolerance=tolerance,
                ).as_dict()

                return USIFStructure(
                    structure_type=StructureType.MOLECULE,
                    storage_mode=StorageMode.SYMMETRIC,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    structure_properties=structure.structure_properties,
                    formula=structure.formula,
                )
        except (ValueError, RuntimeError) as e:
            logger.debug(
                "Molecule optimization failed due to symmetry analysis error: %s", e
            )
        except ValidationError as e:
            logger.warning("Molecule optimization failed due to validation error: %s", e)
        except Exception as e:
            logger.error(
                "Unexpected error during molecule optimization: %s", e, exc_info=True
            )

        return structure
