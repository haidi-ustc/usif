"""pymatgen crystal importer."""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
from usif.constants import StorageMode, StructureType
from usif.exceptions import ValidationError
from usif.interop.common import PymatgenStructureLike
from usif.interop.pymatgen.property_extractor import (
    build_structure_properties,
    crystal_atomic_sites,
    has_atomic_properties,
)
from usif.structures.metadata import SymmetryMetadata
from usif.structures.structure import USIFStructure
from usif.symmetry.analysis import extract_wyckoff_sites, spacegroup_analyzer
from usif.symmetry.equivalence import SymmetryOperations
from usif.symmetry.policies import SymmetryPolicy

logger = logging.getLogger(__name__)


class CrystalImporter:
    """Import pymatgen ``Structure`` objects into USIF."""

    @staticmethod
    def from_pymatgen_structure(
        pmg_structure: PymatgenStructureLike,
        *,
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        symmetry_policy: Optional[SymmetryPolicy] = None,
        **kwargs: Any,
    ) -> USIFStructure:
        """Convert a pymatgen crystal structure to a USIF structure."""
        policy = symmetry_policy or SymmetryPolicy()
        lattice_matrix = pmg_structure.lattice.matrix.copy()
        atomic_payload = has_atomic_properties(forces=forces, charges=charges, magmoms=magmoms)
        try_symmetric, drop_properties = policy.resolve_atomic_properties(
            atomic_payload, "forces/charges/magmoms"
        )
        if drop_properties:
            logger.warning(
                "Dropping per-atom crystal properties because symmetry reduction was requested"
            )
            forces = None
            charges = None
            magmoms = None

        storage_mode = StorageMode.FULL_ATOMIC
        wyckoff_sites = None
        spacegroup_number = 1
        symmetric_lossless = False

        if try_symmetric:
            try:
                spacegroup_number, wyckoff_sites = extract_wyckoff_sites(
                    pmg_structure, symprec=policy.tolerance
                )
                symmetric_lossless = SymmetryOperations.crystal_sites_match(
                    pmg_structure, spacegroup_number, wyckoff_sites
                )
                if policy.mode == "reduce" or symmetric_lossless:
                    storage_mode = StorageMode.SYMMETRIC
                else:
                    wyckoff_sites = None
                    logger.debug(
                        "Symmetric crystal representation does not preserve input coordinates; using full atomic"
                    )
            except (ValueError, RuntimeError) as e:
                logger.warning("Symmetry analysis failed, using full atomic: %s", e)
                wyckoff_sites = None
            except ValidationError as e:
                logger.warning("Symmetric crystal conversion failed validation: %s", e)
                wyckoff_sites = None

        atom_sites = None
        if storage_mode == StorageMode.FULL_ATOMIC:
            try:
                sga = spacegroup_analyzer(pmg_structure, symprec=policy.tolerance)
                spacegroup_number = sga.get_space_group_number()
            except (ValueError, RuntimeError) as e:
                logger.warning("Failed to determine spacegroup: %s", e)
                spacegroup_number = 1
            atom_sites = crystal_atomic_sites(
                pmg_structure,
                forces=forces,
                charges=charges,
                magmoms=magmoms,
            )

        volume = kwargs.pop("volume", pmg_structure.volume)
        metadata = None
        if storage_mode == StorageMode.SYMMETRIC:
            metadata = SymmetryMetadata(
                lossless=bool(symmetric_lossless),
                reconstruction_mode="spacegroup_expansion",
                symmetry_origin="pymatgen_spacegroup",
                source_coordinate_frame="fractional",
                tolerance=policy.tolerance,
            )

        return USIFStructure(
            structure_type=StructureType.CRYSTAL,
            lattice_matrix=lattice_matrix,
            spacegroup=spacegroup_number,
            storage_mode=storage_mode,
            wyckoff_sites=wyckoff_sites,
            atom_sites=atom_sites,
            structure_properties=build_structure_properties(
                energy=energy,
                stress=stress,
                volume=volume,
                custom=kwargs,
                symmetry_metadata=metadata,
            ),
            formula=pmg_structure.composition.reduced_formula,
        )
