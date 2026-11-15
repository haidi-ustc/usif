"""Expand symmetric USIF structures to explicit atoms.

This is the single place where a SYMMETRIC structure becomes FULL_ATOMIC.
Every adapter (matsimpy, pymatgen, ASE, file writers) exports from the result,
so all of them reconstruct identical atoms.
"""

from __future__ import annotations

import copy
import logging
from typing import List, Tuple

import numpy as np

from usif.constants import StorageMode, StructureType
from usif.properties.atomic import AtomicProperties
from usif.structures.sites import AtomSite
from usif.structures.structure import USIFStructure
from usif.symmetry.spacegroup import expand_orbit, setting_operations, xyz_tuple
from usif.symmetry.tables import FORMAT5_POINT_GROUP_ROTATIONS

logger = logging.getLogger(__name__)

#: Cartesian tolerance (Angstrom) for merging images of one molecular site.
MOLECULAR_MERGE_TOLERANCE = 1e-6

Site = Tuple[int, Tuple[float, float, float]]


def _fit_multiplicity(images: np.ndarray, multiplicity: int, label: str) -> np.ndarray:
    if len(images) != multiplicity:
        logger.warning(
            "%s generated %d images but the record declares multiplicity %d; "
            "the record was not stored losslessly",
            label,
            len(images),
            multiplicity,
        )
    return images[:multiplicity]


def _sorted_sites(sites: List[Site]) -> List[Site]:
    # Deterministic order: atomic number, then coordinates. Rounding keeps
    # floating-point noise from reordering otherwise identical results.
    return sorted(sites, key=lambda s: (s[0], tuple(round(c, 8) for c in s[1])))


def expanded_crystal_sites(structure: USIFStructure) -> List[Site]:
    """Return ``(atomic_number, fractional_coords)`` for every atom of a symmetric crystal."""
    hall, P, p = structure.symmetry_setting()
    rotations, translations = setting_operations(hall, P, p)
    sites: List[Site] = []
    for site in structure.wyckoff_sites or []:
        images = expand_orbit(site.coords, rotations, translations)
        images = _fit_multiplicity(
            images, site.multiplicity, f"Wyckoff site Z={site.atomic_number}"
        )
        sites.extend((site.atomic_number, xyz_tuple(image)) for image in images)
    return _sorted_sites(sites)


def expanded_molecule_sites(structure: USIFStructure) -> List[Site]:
    """Return ``(atomic_number, cartesian_coords)`` for every atom of a symmetric molecule."""
    point_group = structure.point_group or "C1"
    rotations = FORMAT5_POINT_GROUP_ROTATIONS.get(point_group)
    if rotations is None:
        logger.warning(
            "Point group %s has no stored operations; repeating representative sites",
            point_group,
        )
    sites: List[Site] = []
    for site in structure.point_group_sites or []:
        coords = np.asarray(site.coords, dtype=float)
        if rotations is None:
            images = np.repeat(coords[None, :], site.multiplicity, axis=0)
        else:
            images_list: List[np.ndarray] = []
            for rotation in rotations:
                image = np.asarray(rotation, dtype=float) @ coords
                if not any(
                    np.linalg.norm(image - u) < MOLECULAR_MERGE_TOLERANCE for u in images_list
                ):
                    images_list.append(image)
            images = _fit_multiplicity(
                np.array(images_list), site.multiplicity, f"Point-group site Z={site.atomic_number}"
            )
        sites.extend((site.atomic_number, xyz_tuple(image)) for image in images)
    return _sorted_sites(sites)


def expand_structure(structure: USIFStructure) -> USIFStructure:
    """Return a FULL_ATOMIC equivalent of ``structure`` (itself if already full)."""
    if structure.storage_mode == StorageMode.FULL_ATOMIC:
        return structure

    if structure.structure_type == StructureType.CRYSTAL:
        sites = expanded_crystal_sites(structure)
    else:
        sites = expanded_molecule_sites(structure)

    atom_sites = [AtomSite(z, coords, AtomicProperties()) for z, coords in sites]
    return USIFStructure(
        structure_type=structure.structure_type,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=(
            None if structure.lattice_matrix is None else np.array(structure.lattice_matrix)
        ),
        spacegroup=structure.spacegroup,
        point_group=structure.point_group,
        atom_sites=atom_sites,
        structure_properties=copy.deepcopy(structure.structure_properties),
        formula=structure.formula,
    )
