"""Symmetry reduction service."""

from __future__ import annotations

import copy
import logging

from usif.constants import StorageMode, StructureType
from usif.exceptions import ValidationError
from usif.structures.metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
from usif.structures.structure import USIFStructure
from usif.symmetry.analysis import extract_point_group_sites, extract_wyckoff_sites
from usif.symmetry.equivalence import SymmetryOperations
from usif.symmetry.policies import SymmetryPolicy

logger = logging.getLogger(__name__)


def _properties_with_metadata(structure: USIFStructure, metadata: SymmetryMetadata):
    """Return copied structure properties carrying symmetry metadata."""
    props = copy.deepcopy(structure.structure_properties)
    props.custom[SYMMETRY_METADATA_KEY] = metadata.as_dict()
    return props


class SymmetryReducer:
    """Convert full atomic USIF structures to symmetric representations."""

    @staticmethod
    def reduce_crystal(structure: USIFStructure, tolerance: float) -> USIFStructure:
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure

        policy = SymmetryPolicy(mode="reduce", tolerance=tolerance)
        try:
            from usif.interop.pymatgen.exporter import PymatgenExporter

            pmg_structure = PymatgenExporter.to_pymatgen(structure)
            spacegroup_number, wyckoff_sites = extract_wyckoff_sites(
                pmg_structure, symprec=policy.tolerance
            )

            lossless = SymmetryOperations.crystal_sites_match(
                pmg_structure, spacegroup_number, wyckoff_sites
            )
            if not lossless:
                logger.debug(
                    "Crystal optimization was not lossless; keeping full atomic structure"
                )
                return structure

            reduced_properties = _properties_with_metadata(
                structure,
                SymmetryMetadata(
                    lossless=True,
                    reconstruction_mode="spacegroup_expansion",
                    symmetry_origin="pymatgen_spacegroup",
                    source_coordinate_frame="fractional",
                    tolerance=policy.tolerance,
                ),
            )

            return USIFStructure(
                structure_type=StructureType.CRYSTAL,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=structure.lattice_matrix,
                spacegroup=spacegroup_number,
                wyckoff_sites=wyckoff_sites,
                structure_properties=reduced_properties,
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

        policy = SymmetryPolicy(mode="reduce", molecular_tolerance=tolerance)
        try:
            from usif.interop.pymatgen.exporter import PymatgenExporter

            pmg_molecule = PymatgenExporter.to_pymatgen(structure)
            point_group, point_group_sites = extract_point_group_sites(
                pmg_molecule, tolerance=policy.molecular_tolerance
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

                reduced_properties = _properties_with_metadata(
                    structure,
                    SymmetryMetadata(
                        lossless=True,
                        reconstruction_mode="point_group_expansion",
                        symmetry_origin="pymatgen_point_group",
                        source_coordinate_frame="cartesian",
                        tolerance=policy.molecular_tolerance,
                    ),
                )

                return USIFStructure(
                    structure_type=StructureType.MOLECULE,
                    storage_mode=StorageMode.SYMMETRIC,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    structure_properties=reduced_properties,
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
