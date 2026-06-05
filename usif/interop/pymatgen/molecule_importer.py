"""pymatgen molecule importer."""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
from usif.constants import StorageMode, StructureType
from usif.exceptions import ValidationError
from usif.interop.common import PymatgenMoleculeLike
from usif.interop.pymatgen.property_extractor import (
    build_structure_properties,
    has_atomic_properties,
    molecule_atomic_sites,
)
from usif.structures.metadata import SymmetryMetadata
from usif.structures.structure import USIFStructure
from usif.symmetry.analysis import extract_point_group_sites
from usif.symmetry.equivalence import SymmetryOperations
from usif.symmetry.policies import SymmetryPolicy

logger = logging.getLogger(__name__)


class MoleculeImporter:
    """Import pymatgen ``Molecule`` objects into USIF."""

    @staticmethod
    def from_pymatgen_molecule(
        pmg_molecule: PymatgenMoleculeLike,
        *,
        forces: Optional[np.ndarray] = None,
        charges: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        symmetry_policy: Optional[SymmetryPolicy] = None,
        **kwargs: Any,
    ) -> USIFStructure:
        """Convert a pymatgen molecule to a USIF structure."""
        policy = symmetry_policy or SymmetryPolicy()
        atomic_payload = has_atomic_properties(forces=forces, charges=charges)
        try_symmetric, drop_properties = policy.resolve_atomic_properties(
            atomic_payload, "forces/charges"
        )
        if drop_properties:
            logger.warning(
                "Dropping per-atom molecule properties because symmetry reduction was requested"
            )
            forces = None
            charges = None

        if try_symmetric:
            try:
                point_group, point_group_sites = extract_point_group_sites(
                    pmg_molecule, tolerance=policy.molecular_tolerance
                )
                total_multiplicity = sum(s.multiplicity for s in point_group_sites)
                can_expand = SymmetryOperations.molecular_sites_match(
                    pmg_molecule, point_group, point_group_sites
                )
                if (
                    total_multiplicity == len(pmg_molecule)
                    and len(point_group_sites) < len(pmg_molecule)
                    and (policy.mode == "reduce" or can_expand)
                ):
                    return USIFStructure(
                        structure_type=StructureType.MOLECULE,
                        storage_mode=StorageMode.SYMMETRIC,
                        point_group=point_group,
                        point_group_sites=point_group_sites,
                        structure_properties=build_structure_properties(
                            energy=energy,
                            custom=kwargs,
                            symmetry_metadata=SymmetryMetadata(
                                lossless=bool(can_expand),
                                reconstruction_mode="point_group_expansion",
                                symmetry_origin="pymatgen_point_group",
                                source_coordinate_frame="cartesian",
                                tolerance=policy.molecular_tolerance,
                            ),
                        ),
                        formula=pmg_molecule.composition.reduced_formula,
                    )
            except (ValueError, RuntimeError) as e:
                logger.debug(
                    "Symmetric molecule conversion failed due to symmetry analysis error: %s",
                    e,
                )
            except ValidationError as e:
                logger.warning(
                    "Symmetric molecule conversion failed due to validation error: %s",
                    e,
                )

        return USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=molecule_atomic_sites(
                pmg_molecule,
                forces=forces,
                charges=charges,
            ),
            structure_properties=build_structure_properties(energy=energy, custom=kwargs),
            formula=pmg_molecule.composition.reduced_formula,
        )
