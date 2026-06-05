"""Materials Project query presets and filters."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

QUERY_GROUPS: List[Dict[str, Any]] = [
    {"chemsys": "Si-Ge", "band_gap": (0.0, 1.0)},
    {"chemsys": "Ga-As", "band_gap": (0.0, 2.0)},
    {"chemsys": "In-P", "band_gap": (0.0, 2.5)},
    {"chemsys": "C-N", "band_gap": (0.0, 6.0)},
    {"chemsys": "Li-Fe-P", "band_gap": (0.0, 1.5)},
    {"chemsys": "Na-Cl", "band_gap": (4.0, 6.0)},
    {"chemsys": "Mg-Si", "band_gap": (0.0, 3.0)},
    {"chemsys": "B-N", "band_gap": (0.0, 6.5)},
    {"chemsys": "Cu-S", "band_gap": (0.0, 2.5)},
    {"elements": ["Al", "Si", "N"], "band_gap": (2.0, 5.0)},
]

SUMMARY_FIELDS = [
    "material_id",
    "formula_pretty",
    "nelements",
    "nsites",
    "elements",
    "band_gap",
    "energy_above_hull",
    "formation_energy_per_atom",
    "energy_per_atom",
    "density",
    "volume",
    "total_magnetization",
    "symmetry",
    "is_magnetic",
    "is_metal",
    "is_gap_direct",
    "is_stable",
    "composition",
    "structure",
]


def build_search_kwargs(
    query: Dict[str, Any],
    min_band_gap: Optional[float] = None,
    max_band_gap: Optional[float] = None,
) -> Dict[str, Any]:
    """Build sanitized keyword arguments for ``materials.summary.search``."""
    search_kwargs = {
        k: v for k, v in query.items() if k in {"chemsys", "elements", "band_gap"}
    }
    if min_band_gap is not None or max_band_gap is not None:
        bg_min = min_band_gap if min_band_gap is not None else 0.0
        bg_max = max_band_gap if max_band_gap is not None else 10.0
        search_kwargs["band_gap"] = (bg_min, bg_max)
    search_kwargs["num_sites"] = (1, 200)
    return search_kwargs
