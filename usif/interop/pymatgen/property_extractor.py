"""Property extraction helpers for pymatgen interop."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from usif.properties.atomic import AtomicProperties
from usif.properties.structure import StructureProperties
from usif.structures.metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
from usif.structures.sites import AtomSite


def has_atomic_properties(
    *,
    forces: Optional[np.ndarray] = None,
    charges: Optional[np.ndarray] = None,
    magmoms: Optional[np.ndarray] = None,
) -> bool:
    """Return whether any per-atom property payload was supplied."""
    return forces is not None or charges is not None or magmoms is not None


def molecule_atomic_sites(
    pmg_molecule,
    *,
    forces: Optional[np.ndarray] = None,
    charges: Optional[np.ndarray] = None,
) -> list[AtomSite]:
    """Build molecule atom sites and attach supported per-atom properties."""
    atom_sites: list[AtomSite] = []
    for i, site in enumerate(pmg_molecule):
        atom_props = AtomicProperties()
        if forces is not None and i < len(forces):
            atom_props.force = tuple(forces[i])
        if charges is not None and i < len(charges):
            atom_props.charge = float(charges[i])
        atom_sites.append(AtomSite(site.specie.Z, tuple(site.coords), atom_props))
    return atom_sites


def crystal_atomic_sites(
    pmg_structure,
    *,
    forces: Optional[np.ndarray] = None,
    charges: Optional[np.ndarray] = None,
    magmoms: Optional[np.ndarray] = None,
) -> list[AtomSite]:
    """Build crystal atom sites and attach supported per-atom properties."""
    atom_sites: list[AtomSite] = []
    for i, site in enumerate(pmg_structure):
        atom_props = AtomicProperties()
        if forces is not None and i < len(forces):
            atom_props.force = tuple(forces[i])
        if charges is not None and i < len(charges):
            atom_props.charge = float(charges[i])
        if magmoms is not None and i < len(magmoms):
            atom_props.magmom = float(magmoms[i])
        atom_sites.append(AtomSite(site.specie.Z, tuple(site.frac_coords), atom_props))
    return atom_sites


def stress_to_voigt(stress: np.ndarray) -> tuple[float, ...]:
    """Normalize 3x3 or six-component stress arrays to USIF Voigt order."""
    stress = np.asarray(stress)
    if stress.shape == (3, 3):
        return (
            float(stress[0, 0]),
            float(stress[1, 1]),
            float(stress[2, 2]),
            float(stress[0, 1]),
            float(stress[1, 2]),
            float(stress[0, 2]),
        )
    return tuple(float(v) for v in stress[:6])


def build_structure_properties(
    *,
    energy: Optional[float] = None,
    stress: Optional[np.ndarray] = None,
    volume: Optional[float] = None,
    custom: Optional[dict[str, Any]] = None,
    symmetry_metadata: Optional[SymmetryMetadata] = None,
) -> StructureProperties:
    """Create ``StructureProperties`` from normalized import inputs."""
    props = StructureProperties()
    if energy is not None:
        props.energy = float(energy)
    if stress is not None:
        props.stress = stress_to_voigt(stress)
    if volume is not None:
        props.volume = float(volume)
    if custom:
        props.custom.update(custom)
    if symmetry_metadata is not None:
        props.custom[SYMMETRY_METADATA_KEY] = symmetry_metadata.as_dict()
    return props
