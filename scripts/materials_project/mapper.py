"""Map Materials Project summary documents to :class:`~usif.model.Structure`.

* ``structure``: a ``Structure.as_dict()`` document (parsed without pymatgen)
  or a pymatgen ``Structure`` (converted by the pymatgen backend);
* numeric summary fields become scalar structure properties with units, so
  datasets can filter on them (``Q.prop("band_gap") > 1``);
* ``energy`` is the total DFT energy of the cell, ``uncorrected_energy_per_atom
  * natoms`` (eV); MP's ``energy_per_atom`` includes the MP2020 compatibility
  corrections and is kept separately, per atom;
* identifiers and flags (``material_id``, ``formula_pretty``, ``is_*``,
  ``symmetry``) are kept as properties too.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Union

import numpy as np

from usif import Cell, Structure
from usif.elements import atomic_number
from usif.errors import ValidationError

__all__ = ["NUMERIC_FIELDS", "convert_mp_to_usif", "structure_from_dict"]

#: Numeric summary fields stored as properties, with their units.
NUMERIC_FIELDS: Dict[str, str] = {
    "band_gap": "eV",
    "energy_per_atom": "eV/atom",
    "uncorrected_energy_per_atom": "eV/atom",
    "formation_energy_per_atom": "eV/atom",
    "energy_above_hull": "eV/atom",
    "density": "g/cm^3",
    "total_magnetization": "μB",  # of the whole cell
}
OTHER_FIELDS = (
    "material_id",
    "formula_pretty",
    "is_magnetic",
    "is_metal",
    "is_stable",
    "is_gap_direct",
)
_SITE_NAMES = {"forces": "force", "charge": "charge", "magmom": "magmom", "velocities": "velocity"}


def _field(doc: Any, key: str) -> Any:
    return doc.get(key) if isinstance(doc, Mapping) else getattr(doc, key, None)


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):  # pydantic models in mp-api documents
        value = value.model_dump()
    if hasattr(value, "value") and not isinstance(value, (str, bytes, dict)):
        value = value.value  # enums
    return str(value) if not isinstance(value, (str, int, float, bool, list, dict)) else value


def structure_from_dict(document: Mapping[str, Any]) -> Structure:
    """Parse a pymatgen/MP ``Structure.as_dict()`` document (ordered sites only)."""
    try:
        lattice = np.array(document["lattice"]["matrix"], dtype=float).reshape(3, 3)
        sites = list(document["sites"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"not a structure document: {exc}") from exc
    numbers: List[int] = []
    frac: List[List[float]] = []
    oxidation: List[Any] = []
    columns: Dict[str, List[Any]] = {}
    for index, site in enumerate(sites):
        species = site.get("species") or []
        if len(species) != 1 or abs(float(species[0].get("occu", 1.0)) - 1.0) > 1e-8:
            raise ValidationError(f"site {index} is disordered; only ordered structures are stored")
        numbers.append(atomic_number(species[0]["element"]))
        frac.append([float(x) for x in site["abc"]])
        oxidation.append(species[0].get("oxidation_state"))
        for name, value in (site.get("properties") or {}).items():
            target = _SITE_NAMES.get(name, name)
            columns.setdefault(target, [None] * len(sites))[index] = value
    structure = Structure.from_fractional(numbers, frac, Cell(lattice))
    if any(o is not None for o in oxidation):
        column = oxidation if None in oxidation else np.array(oxidation, dtype=float)
        structure.arrays["oxidation_state"] = column
    for name, column in columns.items():
        structure.arrays[name] = column
    return structure


def convert_mp_to_usif(doc: Union[Mapping[str, Any], Any]) -> Structure:
    """Convert a Materials Project summary document (dict or mp-api object)."""
    raw = _field(doc, "structure")
    if raw is None:
        raise ValidationError("the Materials Project document has no structure")
    if isinstance(raw, Mapping):
        structure = structure_from_dict(raw)
    else:
        from usif import convert

        structure = convert(raw)
    props = structure.properties
    for name, unit in NUMERIC_FIELDS.items():
        value = _field(doc, name)
        if value is not None:
            props.set(name, float(value), unit=unit)
    uncorrected = _field(doc, "uncorrected_energy_per_atom")
    if uncorrected is not None:
        props.set("energy", float(uncorrected) * structure.natoms, unit="eV")
    for name in OTHER_FIELDS:
        value = _field(doc, name)
        if value is not None:
            props[name] = _plain(value)
    symmetry = _field(doc, "symmetry")
    if symmetry is not None:
        number = _field(symmetry, "number")
        symbol = _field(symmetry, "symbol")
        if number is not None:
            props["spacegroup_number"] = int(number)
        if symbol is not None:
            props["spacegroup_symbol"] = str(symbol)
    return structure
