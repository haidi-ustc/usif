"""pymatgen -> USIF importer."""

import logging
from collections import defaultdict
from typing import Optional, Union

import numpy as np
from pymatgen.core import Molecule as PMGMolecule
from pymatgen.core import Structure as PMGStructure
from pymatgen.symmetry.analyzer import PointGroupAnalyzer, SpacegroupAnalyzer

from usif.constants import StorageMode, StructureType, SymmetryConstants
from usif.exceptions import ValidationError
from usif.properties.atomic import AtomicProperties
from usif.properties.structure import StructureProperties
from usif.structures.metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
from usif.structures.sites import AtomSite, PointGroupSite
from usif.structures.structure import USIFStructure
from usif.symmetry import SymmetryOperations

logger = logging.getLogger(__name__)


class PymatgenImporter:
    """Import pymatgen Structure or Molecule objects into USIF."""

    @staticmethod
    def from_pymatgen(
        pmg_obj: Union[PMGStructure, PMGMolecule],
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        force_symmetric: bool = False,
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        **kwargs,
    ) -> USIFStructure:
        """Convert a pymatgen Structure or Molecule to USIF."""
        if isinstance(pmg_obj, PMGMolecule):
            return PymatgenImporter._from_molecule(
                pmg_obj,
                forces=forces,
                charges=charges,
                energy=energy,
                force_symmetric=force_symmetric,
                drop_atomic_properties=drop_atomic_properties,
                fallback_full_atomic=fallback_full_atomic,
                **kwargs,
            )

        if isinstance(pmg_obj, PMGStructure):
            return PymatgenImporter._from_crystal(
                pmg_obj,
                forces=forces,
                stress=stress,
                energy=energy,
                charges=charges,
                magmoms=magmoms,
                force_symmetric=force_symmetric,
                drop_atomic_properties=drop_atomic_properties,
                fallback_full_atomic=fallback_full_atomic,
                **kwargs,
            )

        raise TypeError(
            f"Expected pymatgen Structure or Molecule, got {type(pmg_obj)!r}"
        )

    @staticmethod
    def _from_molecule(
        pmg_molecule: PMGMolecule,
        forces: Optional[np.ndarray] = None,
        charges: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        force_symmetric: bool = False,
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        **kwargs,
    ) -> USIFStructure:
        """Convert a pymatgen Molecule to USIF."""
        has_atomic_properties = forces is not None or charges is not None
        if drop_atomic_properties and fallback_full_atomic:
            raise ValidationError(
                "drop_atomic_properties and fallback_full_atomic are mutually exclusive"
            )
        if force_symmetric and has_atomic_properties:
            if fallback_full_atomic:
                force_symmetric = False
            elif drop_atomic_properties:
                logger.warning(
                    "Dropping per-atom properties because force_symmetric=True and "
                    "drop_atomic_properties=True"
                )
                forces = None
                charges = None
                has_atomic_properties = False
            else:
                raise ValidationError(
                    "force_symmetric=True cannot preserve per-atom properties "
                    "(forces/charges). Set fallback_full_atomic=True to preserve them "
                    "or drop_atomic_properties=True to explicitly discard them."
                )

        if force_symmetric or (not has_atomic_properties):
            try:
                pga = PointGroupAnalyzer(pmg_molecule)
                point_group = pga.sch_symbol

                atom_groups = defaultdict(list)
                for i, site in enumerate(pmg_molecule):
                    atomic_num = site.specie.Z
                    atom_groups[atomic_num].append((i, np.array(site.coords)))

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

                            if (
                                min_dist
                                < SymmetryConstants.MOLECULAR_EQUIVALENCE_TOLERANCE
                            ):
                                equiv_count += 1
                                used.add(other_idx)

                        point_group_sites.append(
                            PointGroupSite(atomic_num, equiv_count, tuple(coords))
                        )

                total_multiplicity = sum(s.multiplicity for s in point_group_sites)
                can_expand = SymmetryOperations.molecular_sites_match(
                    pmg_molecule, point_group, point_group_sites
                )
                if (
                    total_multiplicity == len(pmg_molecule)
                    and len(point_group_sites) < len(pmg_molecule)
                    and (force_symmetric or can_expand)
                ):
                    struct_props = StructureProperties()
                    if energy is not None:
                        struct_props.energy = energy
                    if kwargs:
                        struct_props.custom.update(kwargs)
                    struct_props.custom[SYMMETRY_METADATA_KEY] = SymmetryMetadata(
                        lossless=bool(can_expand),
                        reconstruction_mode="point_group_expansion",
                        symmetry_origin="pymatgen_point_group",
                        source_coordinate_frame="cartesian",
                        tolerance=SymmetryConstants.MOLECULAR_EQUIVALENCE_TOLERANCE,
                    ).as_dict()

                    return USIFStructure(
                        structure_type=StructureType.MOLECULE,
                        storage_mode=StorageMode.SYMMETRIC,
                        point_group=point_group,
                        point_group_sites=point_group_sites,
                        structure_properties=struct_props,
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

        atom_sites = []
        for i, site in enumerate(pmg_molecule):
            atom_props = AtomicProperties()
            if forces is not None and i < len(forces):
                atom_props.force = tuple(forces[i])
            if charges is not None and i < len(charges):
                atom_props.charge = float(charges[i])
            atom_sites.append(AtomSite(site.specie.Z, tuple(site.coords), atom_props))

        struct_props = StructureProperties()
        if energy is not None:
            struct_props.energy = energy
        if kwargs:
            struct_props.custom.update(kwargs)

        return USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=atom_sites,
            structure_properties=struct_props,
            formula=pmg_molecule.composition.reduced_formula,
        )

    @staticmethod
    def _from_crystal(
        pmg_structure: PMGStructure,
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        force_symmetric: bool = False,
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        **kwargs,
    ) -> USIFStructure:
        """Convert a pymatgen Structure to USIF."""
        lattice_matrix = pmg_structure.lattice.matrix.copy()

        has_atomic_properties = (
            forces is not None or charges is not None or magmoms is not None
        )
        if drop_atomic_properties and fallback_full_atomic:
            raise ValidationError(
                "drop_atomic_properties and fallback_full_atomic are mutually exclusive"
            )
        if force_symmetric and has_atomic_properties:
            if fallback_full_atomic:
                force_symmetric = False
            elif drop_atomic_properties:
                logger.warning(
                    "Dropping per-atom properties because force_symmetric=True and "
                    "drop_atomic_properties=True"
                )
                forces = None
                charges = None
                magmoms = None
                has_atomic_properties = False
            else:
                raise ValidationError(
                    "force_symmetric=True cannot preserve per-atom properties "
                    "(forces/charges/magmoms). Set fallback_full_atomic=True to preserve "
                    "them or drop_atomic_properties=True to explicitly discard them."
                )

        storage_mode = StorageMode.SYMMETRIC if force_symmetric else (
            StorageMode.FULL_ATOMIC if has_atomic_properties else StorageMode.SYMMETRIC
        )
        wyckoff_sites = None
        atom_sites = None
        spacegroup_number = 1
        symmetric_lossless = False

        if storage_mode == StorageMode.SYMMETRIC:
            try:
                from usif.symmetry.analysis import extract_wyckoff_sites

                spacegroup_number, wyckoff_sites = extract_wyckoff_sites(
                    pmg_structure,
                    symprec=SymmetryConstants.DEFAULT_SPACEGROUP_TOLERANCE,
                )
                symmetric_lossless = SymmetryOperations.crystal_sites_match(
                    pmg_structure, spacegroup_number, wyckoff_sites
                )
                if not force_symmetric and not symmetric_lossless:
                    logger.debug(
                        "Symmetric crystal representation does not preserve input coordinates; using full atomic"
                    )
                    storage_mode = StorageMode.FULL_ATOMIC
                    wyckoff_sites = None
            except ValueError as e:
                logger.warning("Symmetry analysis failed, using full atomic: %s", e)
                storage_mode = StorageMode.FULL_ATOMIC
            except RuntimeError as e:
                logger.error("Runtime error in symmetry analysis: %s", e)
                storage_mode = StorageMode.FULL_ATOMIC

        if storage_mode == StorageMode.FULL_ATOMIC:
            try:
                sga = SpacegroupAnalyzer(
                    pmg_structure,
                    symprec=SymmetryConstants.DEFAULT_SPACEGROUP_TOLERANCE,
                )
                spacegroup_number = sga.get_space_group_number()
            except (ValueError, RuntimeError) as e:
                logger.warning("Failed to determine spacegroup: %s", e)
                spacegroup_number = 1

            atom_sites = []
            for i, site in enumerate(pmg_structure):
                atom_props = AtomicProperties()
                if forces is not None and i < len(forces):
                    atom_props.force = tuple(forces[i])
                if charges is not None and i < len(charges):
                    atom_props.charge = float(charges[i])
                if magmoms is not None and i < len(magmoms):
                    atom_props.magmom = float(magmoms[i])
                atom_sites.append(AtomSite(site.specie.Z, tuple(site.frac_coords), atom_props))

        struct_props = StructureProperties()
        if energy is not None:
            struct_props.energy = energy
        if stress is not None:
            if stress.shape == (3, 3):
                struct_props.stress = (
                    stress[0, 0],
                    stress[1, 1],
                    stress[2, 2],
                    stress[0, 1],
                    stress[1, 2],
                    stress[0, 2],
                )
            else:
                struct_props.stress = tuple(stress[:6])

        if "volume" in kwargs:
            struct_props.volume = kwargs.pop("volume")
        else:
            struct_props.volume = pmg_structure.volume

        if kwargs:
            struct_props.custom.update(kwargs)
        if storage_mode == StorageMode.SYMMETRIC:
            struct_props.custom[SYMMETRY_METADATA_KEY] = SymmetryMetadata(
                lossless=bool(symmetric_lossless),
                reconstruction_mode="spacegroup_expansion",
                symmetry_origin="pymatgen_spacegroup",
                source_coordinate_frame="fractional",
                tolerance=SymmetryConstants.DEFAULT_SPACEGROUP_TOLERANCE,
            ).as_dict()

        return USIFStructure(
            structure_type=StructureType.CRYSTAL,
            lattice_matrix=lattice_matrix,
            spacegroup=spacegroup_number,
            storage_mode=storage_mode,
            wyckoff_sites=wyckoff_sites,
            atom_sites=atom_sites,
            structure_properties=struct_props,
            formula=pmg_structure.composition.reduced_formula,
        )
