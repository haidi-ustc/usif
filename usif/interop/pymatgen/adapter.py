"""Optional pymatgen adapter (``pip install usif[pymatgen]``).

pymatgen is imported only when an export is requested; imports only read
attributes of the objects they are given.

Mapping:

* species -> atomic numbers; ``Species`` oxidation states -> per-atom custom
  ``oxidation_state`` (restored on export)
* site properties ``forces``, ``charge``/``charges``, ``magmom``,
  ``velocities`` -> USIF per-atom ``force``/``charge``/``magmom``/``velocity``;
  any other site property -> per-atom custom value
* ``Molecule.charge`` / ``spin_multiplicity`` -> structure custom values
* disordered (partially occupied) sites are rejected
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from usif.exceptions import ValidationError
from usif.interop.common.arrays import AtomsData, structure_to_arrays
from usif.interop.common.importing import import_atoms
from usif.interop.common.type_guards import is_pymatgen_molecule, is_pymatgen_structure
from usif.structures.structure import USIFStructure
from usif.symmetry.policies import SymmetryPolicy

OXIDATION_STATE_KEY = "oxidation_state"
MOLECULE_CHARGE_KEY = "charge"
SPIN_MULTIPLICITY_KEY = "spin_multiplicity"

#: pymatgen site-property name -> USIF per-atom property name
_SITE_PROPERTY_MAP = {
    "forces": "force",
    "force": "force",
    "charge": "charge",
    "charges": "charge",
    "magmom": "magmom",
    "velocities": "velocity",
}
#: USIF per-atom property name -> pymatgen site-property name on export
_EXPORT_NAMES = {
    "force": "forces",
    "charge": "charge",
    "magmom": "magmom",
    "velocity": "velocities",
}


def _require_pymatgen():
    try:
        import pymatgen.core as pmg_core
    except ImportError as exc:
        raise ImportError(
            "pymatgen conversion requires pymatgen: pip install usif[pymatgen]"
        ) from exc
    return pmg_core


def _to_json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "tolist"):  # pymatgen Magmom and similar array-likes
        return value.tolist()
    return value


def _atoms_from_pymatgen(obj: Any, *, periodic: bool) -> AtomsData:
    if not obj.is_ordered:
        raise ValidationError(
            "Disordered (partially occupied) structures are not supported by USIF; "
            "order the structure first (e.g. with an ordering transformation)."
        )
    numbers: List[int] = []
    site_custom: List[Dict[str, Any]] = []
    for site in obj:
        specie = site.specie
        numbers.append(int(specie.Z))
        extra: Dict[str, Any] = {}
        oxidation = getattr(specie, "oxi_state", None)
        if oxidation is not None:
            extra[OXIDATION_STATE_KEY] = float(oxidation)
        site_custom.append(extra)

    atomic: Dict[str, List[Any]] = {}
    for name, values in (obj.site_properties or {}).items():
        values = [_to_json_value(v) for v in values]
        target = _SITE_PROPERTY_MAP.get(name)
        scalar_target = target in ("charge", "magmom")
        if target and not (scalar_target and any(np.ndim(v) != 0 for v in values if v is not None)):
            atomic[target] = values
        else:  # unknown names and non-collinear magmoms stay per-atom custom data
            for extra, value in zip(site_custom, values):
                if value is not None:
                    extra[name] = value

    custom: Dict[str, Any] = {}
    lattice = None
    pbc = (False, False, False)
    if periodic:
        lattice = np.array(obj.lattice.matrix, dtype=float)
        pbc = tuple(bool(p) for p in getattr(obj.lattice, "pbc", (True, True, True)))  # type: ignore[assignment]
    else:
        charge = float(getattr(obj, "charge", 0.0) or 0.0)
        spin = getattr(obj, "spin_multiplicity", None)
        if charge != 0.0:
            custom[MOLECULE_CHARGE_KEY] = charge
        if spin is not None and int(spin) != 1:
            custom[SPIN_MULTIPLICITY_KEY] = int(spin)

    return AtomsData(
        numbers=numbers,
        positions=np.array(obj.cart_coords, dtype=float).reshape(len(numbers), 3),
        lattice=lattice,
        pbc=pbc,
        atomic=atomic,
        site_custom=site_custom,
        custom=custom,
    )


class PymatgenImporter:
    """Convert pymatgen ``Structure``/``Molecule`` objects to USIF."""

    @staticmethod
    def from_pymatgen(
        pmg_obj: Any,
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
        """Convert a pymatgen ``Structure`` or ``Molecule``.

        Extra keyword arguments are stored as structure-level custom properties.
        """
        if is_pymatgen_molecule(pmg_obj):
            data = _atoms_from_pymatgen(pmg_obj, periodic=False)
        elif is_pymatgen_structure(pmg_obj):
            data = _atoms_from_pymatgen(pmg_obj, periodic=True)
        else:
            raise TypeError(
                "Expected pymatgen Structure or Molecule, "
                f"got {type(pmg_obj).__module__}.{type(pmg_obj).__qualname__}"
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


class PymatgenExporter:
    """Convert USIF structures to pymatgen objects."""

    @staticmethod
    def to_pymatgen(structure: USIFStructure) -> Any:
        """Return a pymatgen ``Structure`` (crystals) or ``Molecule`` (molecules)."""
        pmg_core = _require_pymatgen()
        data = structure_to_arrays(structure)

        species: List[Any] = []
        for z, extra in zip(data.numbers, data.site_custom or [{}] * len(data.numbers)):
            element = pmg_core.Element.from_Z(z)
            oxidation = extra.get(OXIDATION_STATE_KEY)
            species.append(
                pmg_core.Species(element.symbol, oxidation) if oxidation is not None else element
            )

        site_properties: Dict[str, List[Any]] = {}
        for name, values in data.atomic.items():
            site_properties[_EXPORT_NAMES[name]] = values
        custom_keys = sorted(
            {key for extra in data.site_custom for key in extra if key != OXIDATION_STATE_KEY}
        )
        for key in custom_keys:
            site_properties[key] = [extra.get(key) for extra in data.site_custom]

        if data.is_crystal:
            lattice = pmg_core.Lattice(data.lattice, pbc=data.pbc)
            return pmg_core.Structure(
                lattice,
                species,
                data.positions,
                coords_are_cartesian=True,
                site_properties=site_properties or None,
            )
        charge = float(data.custom.get(MOLECULE_CHARGE_KEY, 0.0))
        spin = data.custom.get(SPIN_MULTIPLICITY_KEY)
        return pmg_core.Molecule(
            species,
            data.positions,
            charge=charge,
            spin_multiplicity=int(spin) if spin is not None else None,
            site_properties=site_properties or None,
        )
