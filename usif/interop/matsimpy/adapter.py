"""Optional matsimpy adapter (``pip install usif[matsimpy]``).

Mapping:

* ``Crystal`` -> USIF crystal (``lattice.matrix`` rows are lattice vectors,
  as in USIF), ``Molecule`` -> USIF molecule
* per-site dict keys ``force``/``forces``, ``charge``, ``magmom``,
  ``velocity``/``velocities`` -> USIF per-atom properties; other keys ->
  per-atom custom values (restored on export)
* ``metadata``: ``energy`` and ``stress`` (GPa) map to USIF structure
  properties, other JSON-compatible entries become structure custom values
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from usif.elements import atomic_number, element_symbol
from usif.interop.common.arrays import AtomsData, structure_to_arrays, voigt_to_tensor
from usif.interop.common.importing import import_atoms
from usif.interop.common.type_guards import is_matsimpy_crystal, is_matsimpy_molecule
from usif.properties.values import normalize_json_value
from usif.structures.structure import USIFStructure
from usif.symmetry.policies import SymmetryPolicy

logger = logging.getLogger(__name__)

_SITE_KEY_MAP = {
    "force": "force",
    "forces": "force",
    "charge": "charge",
    "magmom": "magmom",
    "velocity": "velocity",
    "velocities": "velocity",
}


def _require_matsimpy():
    try:
        import matsimpy
    except ImportError as exc:
        raise ImportError(
            "matsimpy conversion requires matsimpy: pip install usif[matsimpy]"
        ) from exc
    return matsimpy


def _species_number(specie: Any) -> int:
    if isinstance(specie, (int, np.integer)):
        return int(specie)
    symbol = getattr(specie, "symbol", specie)
    return atomic_number(str(symbol))


def _atoms_from_matsimpy(obj: Any, *, periodic: bool) -> AtomsData:
    numbers = [_species_number(s) for s in obj.species]
    count = len(numbers)

    atomic: Dict[str, List[Any]] = {}
    site_custom: List[Dict[str, Any]] = [{} for _ in range(count)]
    for index, props in enumerate(obj.site_properties or ()):
        for key, value in (props or {}).items():
            value = normalize_json_value(value)
            target = _SITE_KEY_MAP.get(key)
            if target is not None and value is not None:
                atomic.setdefault(target, [None] * count)[index] = value
            elif value is not None:
                site_custom[index][key] = value

    metadata = dict(getattr(obj, "metadata", None) or {})
    energy = metadata.pop("energy", None)
    stress = metadata.pop("stress", None)
    custom: Dict[str, Any] = {}
    for key, value in metadata.items():
        try:
            custom[str(key)] = normalize_json_value(value)
        except (TypeError, ValueError):
            logger.debug("Skipping non-JSON matsimpy metadata entry %r", key)

    lattice = None
    pbc = (False, False, False)
    if periodic:
        lattice = np.array(obj.lattice.matrix, dtype=float)
        pbc = tuple(bool(p) for p in getattr(obj, "pbc", (True, True, True)))  # type: ignore[assignment]

    return AtomsData(
        numbers=numbers,
        positions=np.array(obj.positions, dtype=float).reshape(count, 3),
        lattice=lattice,
        pbc=pbc,
        atomic=atomic,
        site_custom=site_custom,
        energy=float(energy) if energy is not None else None,
        stress=None if stress is None else tuple(np.asarray(stress, dtype=float).ravel()),
        custom=custom,
    )


class MatsimpyImporter:
    """Convert matsimpy ``Crystal``/``Molecule`` objects to USIF."""

    @staticmethod
    def from_matsimpy(
        obj: Any,
        /,
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        force_symmetric: bool = False,
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        symmetry_policy: Optional[SymmetryPolicy] = None,
        **kwargs: Any,
    ) -> USIFStructure:
        """Convert a matsimpy ``Crystal`` or ``Molecule``."""
        if is_matsimpy_crystal(obj):
            data = _atoms_from_matsimpy(obj, periodic=True)
        elif is_matsimpy_molecule(obj):
            data = _atoms_from_matsimpy(obj, periodic=False)
        else:
            raise TypeError(
                "Expected matsimpy Crystal or Molecule, "
                f"got {type(obj).__module__}.{type(obj).__qualname__}"
            )
        return import_atoms(
            data,
            forces=forces,
            stress=stress,
            energy=energy,
            charges=charges,
            magmoms=magmoms,
            force_symmetric=force_symmetric,
            drop_atomic_properties=drop_atomic_properties,
            fallback_full_atomic=fallback_full_atomic,
            symmetry_policy=symmetry_policy,
            custom=kwargs,
        )


class MatsimpyExporter:
    """Convert USIF structures to matsimpy objects."""

    @staticmethod
    def to_matsimpy(structure: USIFStructure) -> Any:
        """Return a matsimpy ``Crystal`` (crystals) or ``Molecule`` (molecules)."""
        matsimpy = _require_matsimpy()
        data = structure_to_arrays(structure)
        species = [element_symbol(z) for z in data.numbers]

        site_properties: List[Dict[str, Any]] = []
        for index in range(len(species)):
            props = dict(data.site_custom[index]) if data.site_custom else {}
            for name, values in data.atomic.items():
                if values[index] is not None:
                    props[name] = values[index]
            site_properties.append(props)
        has_site_properties = any(site_properties)

        metadata: Dict[str, Any] = dict(data.custom)
        if data.energy is not None:
            metadata["energy"] = data.energy
        if data.stress is not None:
            metadata["stress"] = voigt_to_tensor(data.stress).tolist()

        if data.is_crystal:
            return matsimpy.Crystal(
                species,
                data.positions.tolist(),
                matsimpy.Lattice(data.lattice),
                pbc=list(data.pbc),
                coords_are_cartesian=True,
                site_properties=site_properties if has_site_properties else None,
                metadata=metadata or None,
            )
        return matsimpy.Molecule(
            species,
            data.positions.tolist(),
            site_properties=site_properties if has_site_properties else None,
            metadata=metadata or None,
        )
