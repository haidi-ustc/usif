"""Typed property extraction helpers for pymatgen interop."""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np

from usif.interop.common import PymatgenMoleculeLike, PymatgenStructureLike
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


def _as_array_or_none(values: Optional[np.ndarray], *, name: str, site_count: int) -> Optional[np.ndarray]:
    """Normalize optional per-site payload and validate its leading dimension."""
    if values is None:
        return None
    array = np.asarray(values)
    if len(array) != site_count:
        raise ValueError(
            f"{name} length must match the number of sites ({site_count}), got {len(array)}"
        )
    return array


def _site_atomic_number(site: Any) -> int:
    return int(site.specie.Z)


def molecule_atomic_sites(
    pmg_molecule: PymatgenMoleculeLike,
    *,
    forces: Optional[np.ndarray] = None,
    charges: Optional[np.ndarray] = None,
) -> list[AtomSite]:
    """Build molecule atom sites and attach supported per-atom properties."""
    site_count = len(pmg_molecule)
    forces_array = _as_array_or_none(forces, name="forces", site_count=site_count)
    charges_array = _as_array_or_none(charges, name="charges", site_count=site_count)

    atom_sites: list[AtomSite] = []
    for i, site in enumerate(pmg_molecule):
        atom_props = AtomicProperties()
        if forces_array is not None:
            atom_props.set_vector("force", tuple(float(v) for v in forces_array[i]))
        if charges_array is not None:
            atom_props.set_scalar("charge", float(charges_array[i]))
        atom_sites.append(AtomSite(_site_atomic_number(site), tuple(float(v) for v in site.coords), atom_props))
    return atom_sites


def crystal_atomic_sites(
    pmg_structure: PymatgenStructureLike,
    *,
    forces: Optional[np.ndarray] = None,
    charges: Optional[np.ndarray] = None,
    magmoms: Optional[np.ndarray] = None,
) -> list[AtomSite]:
    """Build crystal atom sites and attach supported per-atom properties."""
    site_count = len(pmg_structure)
    forces_array = _as_array_or_none(forces, name="forces", site_count=site_count)
    charges_array = _as_array_or_none(charges, name="charges", site_count=site_count)
    magmoms_array = _as_array_or_none(magmoms, name="magmoms", site_count=site_count)

    atom_sites: list[AtomSite] = []
    for i, site in enumerate(pmg_structure):
        atom_props = AtomicProperties()
        if forces_array is not None:
            atom_props.set_vector("force", tuple(float(v) for v in forces_array[i]))
        if charges_array is not None:
            atom_props.set_scalar("charge", float(charges_array[i]))
        if magmoms_array is not None:
            atom_props.set_scalar("magmom", float(magmoms_array[i]))
        atom_sites.append(
            AtomSite(_site_atomic_number(site), tuple(float(v) for v in site.frac_coords), atom_props)
        )
    return atom_sites


def stress_to_voigt(stress: np.ndarray | Sequence[float] | Sequence[Sequence[float]]) -> tuple[float, ...]:
    """Normalize 3x3 or six-component stress arrays to USIF Voigt order.

    USIF stores stress in ``(xx, yy, zz, yz, xz, xy)`` order, matching the
    structure-property tensor helpers introduced for 6.x.
    """
    array = np.asarray(stress, dtype=float)
    if array.shape == (3, 3):
        return (
            float(array[0, 0]),
            float(array[1, 1]),
            float(array[2, 2]),
            float(array[1, 2]),
            float(array[0, 2]),
            float(array[0, 1]),
        )
    flat = array.reshape(-1)
    if flat.shape[0] != 6:
        raise ValueError(f"stress must be a 3x3 tensor or a 6-component vector, got shape {array.shape}")
    return tuple(float(v) for v in flat)


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
        props.set_scalar("energy", float(energy))
    if stress is not None:
        props.set_tensor("stress", stress_to_voigt(stress))
    if volume is not None:
        props.set_scalar("volume", float(volume))
    if custom:
        for key, value in dict(custom).items():
            props.set_custom(key, value)
    if symmetry_metadata is not None:
        props.set_custom(SYMMETRY_METADATA_KEY, symmetry_metadata.as_dict())
    return props
