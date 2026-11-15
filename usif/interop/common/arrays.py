"""Backend-neutral conversion between plain arrays and :class:`USIFStructure`.

Every adapter (matsimpy, pymatgen, ASE) converts its objects to and from this
array form, so importing and exporting behave identically whatever library a
structure came from. Only numpy is required.

Per-atom properties use USIF's canonical names: ``force`` (eV/Å, 3-vector),
``charge`` (e), ``magmom`` (μB), ``velocity`` (3-vector). Anything else is a
per-atom custom value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from usif.constants import StorageMode, StructureType
from usif.exceptions import ValidationError
from usif.formula import reduced_formula
from usif.properties.atomic import AtomicProperties
from usif.properties.structure import StructureProperties
from usif.structures.sites import AtomSite
from usif.structures.structure import USIFStructure

ATOMIC_FIELDS = ("force", "charge", "magmom", "velocity")
_VECTOR_FIELDS = {"force", "velocity"}

#: Structure-level custom key holding periodic boundary flags when they are not
#: all true (slabs, wires, boxed molecules); exporters restore them.
PBC_KEY = "pbc"


@dataclass
class AtomsData:
    """A structure as plain arrays.

    ``positions`` are always Cartesian Ångström. ``atomic`` maps canonical
    per-atom property names to per-atom lists in which ``None`` means "not set
    for this atom"; a name is present only if at least one atom has a value.
    """

    numbers: List[int]
    positions: np.ndarray
    lattice: Optional[np.ndarray] = None
    pbc: Tuple[bool, bool, bool] = (True, True, True)
    atomic: Dict[str, List[Any]] = field(default_factory=dict)
    site_custom: List[Dict[str, Any]] = field(default_factory=list)
    energy: Optional[float] = None
    stress: Optional[Tuple[float, ...]] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_crystal(self) -> bool:
        return self.lattice is not None

    @property
    def frac_positions(self) -> np.ndarray:
        if self.lattice is None:
            raise ValueError("Molecules have no fractional coordinates")
        return self.positions @ np.linalg.inv(self.lattice)

    def atomic_array(self, name: str, fill: Any = 0.0) -> Optional[np.ndarray]:
        """Per-atom values as an array (missing atoms filled with ``fill``), or None."""
        values = self.atomic.get(name)
        if values is None:
            return None
        width = 3 if name in _VECTOR_FIELDS else None
        default = [fill] * 3 if width else fill
        return np.array([default if v is None else v for v in values], dtype=float)


def stress_to_voigt(stress: Any) -> Tuple[float, ...]:
    """Normalize a 3x3 tensor or 6-vector to USIF Voigt order (xx, yy, zz, yz, xz, xy)."""
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
        raise ValueError(
            f"stress must be a 3x3 tensor or a 6-component vector, got shape {array.shape}"
        )
    return tuple(float(v) for v in flat)


def voigt_to_tensor(voigt: Sequence[float]) -> np.ndarray:
    xx, yy, zz, yz, xz, xy = (float(v) for v in voigt)
    return np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])


def _per_atom(name: str, values: Any, count: int) -> List[Any]:
    if isinstance(values, np.ndarray):
        values = values.tolist()
    values = list(values)
    if len(values) != count:
        raise ValidationError(f"{name} has {len(values)} entries for {count} atoms")
    return values


def build_structure(
    numbers: Sequence[int],
    positions: Any,
    *,
    lattice: Any = None,
    cartesian: bool = True,
    pbc: Optional[Sequence[bool]] = None,
    atomic: Optional[Mapping[str, Any]] = None,
    site_custom: Optional[Sequence[Mapping[str, Any]]] = None,
    energy: Optional[float] = None,
    stress: Any = None,
    custom: Optional[Mapping[str, Any]] = None,
) -> USIFStructure:
    """Build a FULL_ATOMIC :class:`USIFStructure` from arrays.

    A structure with a lattice is a crystal (coordinates stored fractional);
    without one it is a molecule (Cartesian). Atom order is preserved.
    """
    numbers = [int(z) for z in numbers]
    count = len(numbers)
    if count == 0:
        raise ValidationError("A structure needs at least one atom")
    if any(not 1 <= z <= 118 for z in numbers):
        raise ValidationError("Atomic numbers must be in 1..118")
    coords = np.asarray(positions, dtype=float).reshape(count, 3)
    if not np.all(np.isfinite(coords)):
        raise ValidationError("Atomic positions must be finite")

    lattice_matrix = None
    if lattice is not None:
        lattice_matrix = np.asarray(lattice, dtype=float).reshape(3, 3)
        if abs(np.linalg.det(lattice_matrix)) < 1e-8:
            lattice_matrix = None  # degenerate/empty cell: treat as a molecule
    if lattice_matrix is not None and cartesian:
        coords = coords @ np.linalg.inv(lattice_matrix)

    per_atom: Dict[str, List[Any]] = {}
    for name, values in (atomic or {}).items():
        if name not in ATOMIC_FIELDS:
            raise ValidationError(f"Unknown per-atom property {name!r}; use site_custom")
        if values is not None:
            per_atom[name] = _per_atom(name, values, count)
    customs = [dict(c) for c in site_custom] if site_custom is not None else [{}] * count
    if len(customs) != count:
        raise ValidationError(f"site_custom has {len(customs)} entries for {count} atoms")

    atom_sites = []
    for i, z in enumerate(numbers):
        props = AtomicProperties()
        for name, values in per_atom.items():
            value = values[i]
            if value is None:
                continue
            if name in _VECTOR_FIELDS:
                props.set_vector(name, tuple(float(v) for v in value))
            else:
                props.set_scalar(name, float(value))
        for key, value in customs[i].items():
            props.set_custom(key, value)
        atom_sites.append(
            AtomSite(z, (float(coords[i, 0]), float(coords[i, 1]), float(coords[i, 2])), props)
        )

    structure_props = StructureProperties()
    if energy is not None:
        structure_props.set_scalar("energy", float(energy))
    if stress is not None:
        structure_props.set_tensor("stress", stress_to_voigt(stress))
    if lattice_matrix is not None:
        structure_props.set_scalar("volume", float(abs(np.linalg.det(lattice_matrix))))
    for key, value in dict(custom or {}).items():
        structure_props.set_custom(key, value)
    if lattice_matrix is not None and pbc is not None and not all(bool(p) for p in pbc):
        structure_props.set_custom(PBC_KEY, [bool(p) for p in pbc])

    return USIFStructure(
        structure_type=(
            StructureType.CRYSTAL if lattice_matrix is not None else StructureType.MOLECULE
        ),
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=lattice_matrix,
        atom_sites=atom_sites,
        structure_properties=structure_props,
        formula=reduced_formula(numbers),
    )


def structure_to_arrays(structure: USIFStructure) -> AtomsData:
    """Return the explicit atoms of ``structure`` (symmetric storage is expanded)."""
    from usif.symmetry.expand import expand_structure

    full = expand_structure(structure)
    sites = full.atom_sites or []
    numbers = [site.atomic_number for site in sites]
    coords = np.array([site.coords for site in sites], dtype=float).reshape(len(sites), 3)

    lattice = None
    pbc: Tuple[bool, bool, bool] = (False, False, False)
    if full.is_crystal():
        lattice = np.array(full.lattice_matrix, dtype=float)
        coords = coords @ lattice
        stored_pbc = full.structure_properties.custom.get(PBC_KEY)
        pbc = tuple(bool(p) for p in stored_pbc) if stored_pbc else (True, True, True)  # type: ignore[assignment]

    atomic: Dict[str, List[Any]] = {}
    for name in ATOMIC_FIELDS:
        values = [getattr(site.properties, name) for site in sites]
        if any(v is not None for v in values):
            atomic[name] = [
                None if v is None else (list(v) if name in _VECTOR_FIELDS else v) for v in values
            ]

    props = full.structure_properties
    custom = {k: v for k, v in props.custom.items() if k != PBC_KEY}
    return AtomsData(
        numbers=numbers,
        positions=coords,
        lattice=lattice,
        pbc=pbc,
        atomic=atomic,
        site_custom=[dict(site.properties.custom) for site in sites],
        energy=props.energy,
        stress=tuple(props.stress) if props.stress is not None else None,
        custom=custom,
    )
