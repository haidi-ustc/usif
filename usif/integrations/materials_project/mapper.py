"""Map Materials Project summary documents to USIF structures."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

import numpy as np

from usif.elements import atomic_number
from usif.exceptions import ValidationError
from usif.interop.common.arrays import AtomsData
from usif.interop.common.importing import import_atoms
from usif.interop.pymatgen.adapter import OXIDATION_STATE_KEY, _SITE_PROPERTY_MAP
from usif.structures.structure import USIFStructure

CUSTOM_FIELDS = (
    "band_gap",
    "density",
    "total_magnetization",
    "is_magnetic",
    "is_metal",
    "is_stable",
    "material_id",
    "formula_pretty",
)


def _get_value(doc: Union[Dict[str, Any], Any], key: str) -> Any:
    if isinstance(doc, dict):
        return doc.get(key)
    return getattr(doc, key, None)


def atoms_from_structure_dict(structure: Dict[str, Any]) -> AtomsData:
    """Parse a Materials Project / pymatgen ``Structure.as_dict()`` document.

    Needs no pymatgen. Only ordered structures (one species with occupancy 1
    per site) are supported.
    """
    try:
        lattice = np.array(structure["lattice"]["matrix"], dtype=float).reshape(3, 3)
        sites = structure["sites"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Not a structure document: {exc}") from exc

    numbers: List[int] = []
    frac: List[List[float]] = []
    site_custom: List[Dict[str, Any]] = []
    atomic: Dict[str, List[Any]] = {}
    for index, site in enumerate(sites):
        species = site.get("species") or []
        if len(species) != 1 or abs(float(species[0].get("occu", 1.0)) - 1.0) > 1e-8:
            raise ValidationError(
                f"Site {index} is disordered (partially occupied); USIF stores ordered structures only"
            )
        specie = species[0]
        numbers.append(atomic_number(specie["element"]))
        frac.append([float(x) for x in site["abc"]])
        extra: Dict[str, Any] = {}
        if specie.get("oxidation_state") is not None:
            extra[OXIDATION_STATE_KEY] = float(specie["oxidation_state"])
        for name, value in (site.get("properties") or {}).items():
            target = _SITE_PROPERTY_MAP.get(name)
            if target is not None and value is not None and (
                target not in ("charge", "magmom") or np.ndim(value) == 0
            ):
                atomic.setdefault(target, [None] * len(sites))[index] = value
            elif value is not None:
                extra[name] = value
        site_custom.append(extra)

    return AtomsData(
        numbers=numbers,
        positions=np.array(frac, dtype=float).reshape(len(numbers), 3) @ lattice,
        lattice=lattice,
        atomic=atomic,
        site_custom=site_custom,
    )


def _extract_properties(doc: Union[Dict[str, Any], Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    built_in: Dict[str, Any] = {}
    custom: Dict[str, Any] = {}

    formation_energy_per_atom = _get_value(doc, "formation_energy_per_atom")
    nsites = _get_value(doc, "nsites")
    if formation_energy_per_atom is not None and nsites is not None:
        built_in["energy"] = formation_energy_per_atom * nsites

    volume = _get_value(doc, "volume")
    if volume is not None:
        built_in["volume"] = volume

    for field in CUSTOM_FIELDS:
        value = _get_value(doc, field)
        if value is not None:
            custom[field] = value

    return built_in, custom


def convert_mp_to_usif(doc: Union[Dict[str, Any], Any]) -> USIFStructure:
    """Convert a Materials Project summary document to ``USIFStructure``.

    ``doc["structure"]`` may be a structure dictionary (parsed natively) or a
    pymatgen ``Structure`` as returned by mp-api (converted with the optional
    pymatgen adapter).
    """
    structure = _get_value(doc, "structure")
    if structure is None:
        raise ValueError("Materials Project document does not contain structure data")
    built_in, custom = _extract_properties(doc)

    if isinstance(structure, dict):
        usif_structure = import_atoms(
            atoms_from_structure_dict(structure), energy=built_in.get("energy")
        )
    else:
        from usif.services import import_structure

        usif_structure = import_structure(structure, energy=built_in.get("energy"))

    if built_in.get("volume") is not None:
        usif_structure.structure_properties.set_scalar("volume", float(built_in["volume"]))
    if custom:
        usif_structure.structure_properties.custom.update(custom)
    return usif_structure
