"""Shared import pipeline: adapter arrays -> USIFStructure -> symmetry policy."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from usif.interop.common.arrays import AtomsData, build_structure
from usif.structures.structure import USIFStructure
from usif.symmetry.policies import SymmetryPolicy, apply_symmetry_policy


def import_atoms(
    data: AtomsData,
    *,
    forces: Any = None,
    stress: Any = None,
    energy: Optional[float] = None,
    charges: Any = None,
    magmoms: Any = None,
    force_symmetric: bool = False,
    drop_atomic_properties: bool = False,
    fallback_full_atomic: bool = False,
    symmetry_policy: Optional[SymmetryPolicy] = None,
    custom: Optional[Mapping[str, Any]] = None,
) -> USIFStructure:
    """Build a structure from adapter arrays and apply the symmetry policy.

    Explicit ``forces``/``charges``/``magmoms``/``energy``/``stress`` override
    values found on the source object; ``custom`` entries become structure-level
    custom properties.
    """
    atomic = dict(data.atomic)
    if forces is not None:
        atomic["force"] = forces
    if charges is not None:
        atomic["charge"] = charges
    if magmoms is not None:
        atomic["magmom"] = magmoms

    structure_custom = dict(data.custom)
    structure_custom.update(custom or {})

    structure = build_structure(
        data.numbers,
        data.positions,
        lattice=data.lattice,
        cartesian=True,
        pbc=data.pbc,
        atomic=atomic,
        site_custom=data.site_custom or None,
        energy=energy if energy is not None else data.energy,
        stress=stress if stress is not None else data.stress,
        custom=structure_custom,
    )
    policy = symmetry_policy or SymmetryPolicy.from_import_flags(
        force_symmetric=force_symmetric,
        drop_atomic_properties=drop_atomic_properties,
        fallback_full_atomic=fallback_full_atomic,
    )
    return apply_symmetry_policy(structure, policy)
