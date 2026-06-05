"""Map Materials Project summary documents to USIF structures."""

from __future__ import annotations

from typing import Any, Dict, Tuple, Union

from usif.services import import_pymatgen
from usif.structures.structure import USIFStructure

from .dependencies import require_pymatgen_structure

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


def _extract_structure(doc: Union[Dict[str, Any], Any]) -> Any:
    structure = _get_value(doc, "structure")
    if structure is None:
        raise ValueError("Materials Project document does not contain structure data")
    if isinstance(structure, dict):
        Structure = require_pymatgen_structure()
        return Structure.from_dict(structure)
    return structure


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
    """Convert a Materials Project summary document to ``USIFStructure``."""
    structure = _extract_structure(doc)
    built_in, custom = _extract_properties(doc)

    usif_structure = import_pymatgen(
        structure,
        energy=built_in.get("energy"),
        volume=built_in.get("volume"),
    )
    if custom:
        usif_structure.structure_properties.custom.update(custom)
    return usif_structure
