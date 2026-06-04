"""Symmetry reduction service."""

import logging
from collections import defaultdict

import numpy as np
from pymatgen.symmetry.analyzer import PointGroupAnalyzer, SpacegroupAnalyzer

from usif.constants import StorageMode, StructureType
from usif.exceptions import ValidationError
from usif.structures.metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
from usif.structures.sites import PointGroupSite, WyckoffSite
from usif.structures.structure import USIFStructure
from usif.symmetry.equivalence import SymmetryOperations

logger = logging.getLogger(__name__)

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

            spacegroup_number = sga.get_space_group_number()
            lossless = SymmetryOperations.crystal_sites_match(
                pmg_structure, spacegroup_number, wyckoff_sites
            )
            if not lossless:
                logger.debug(
                    "Crystal optimization was not lossless; keeping full atomic structure"
                )
                return structure

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
                spacegroup=spacegroup_number,
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
                lossless = SymmetryOperations.molecular_sites_match(
                    pmg_molecule, point_group, point_group_sites
                )
                if not lossless:
                    logger.debug(
                        "Molecule optimization was not lossless; keeping full atomic structure"
                    )
                    return structure

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
