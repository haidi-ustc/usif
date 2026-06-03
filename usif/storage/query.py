"""Query helpers for USIF containers."""

from typing import Any, Dict, Optional, Set, Tuple

from usif.constants import SymmetryConstants


class QueryEngine:
    """Resolve container query filters against pre-built indexes."""

    def __init__(self, indexes, group_getter):
        self.indexes = indexes
        self.group_getter = group_getter

    def candidate_hashes(
        self,
        formula: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        energy_range: Optional[Tuple[float, float]] = None,
        group: Optional[str] = None,
    ) -> Set[str]:
        if formula:
            candidates = set(self.indexes.formula_index.get(formula, []))
        else:
            candidates = set(self.indexes.hash_index.keys())

        if properties:
            for prop_name, prop_value in properties.items():
                prop_index = self.indexes.property_index.get(prop_name)
                if not prop_index:
                    candidates.clear()
                    break
                if isinstance(prop_value, (int, float)):
                    matches = set()
                    for bucket, hashes in prop_index.items():
                        if (
                            isinstance(bucket, (int, float))
                            and abs(bucket - prop_value)
                            < SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE
                        ):
                            matches.update(hashes)
                    candidates.intersection_update(matches)
                else:
                    candidates.intersection_update(prop_index.get(prop_value, []))

        if energy_range:
            min_energy, max_energy = energy_range
            energy_hashes = set()
            for bucket, hashes in self.indexes.property_index.get("energy", {}).items():
                if isinstance(bucket, (int, float)) and min_energy <= bucket <= max_energy:
                    energy_hashes.update(hashes)
            candidates.intersection_update(energy_hashes)

        if group and group != "/":
            target_group = self.group_getter(group)
            group_hashes = set(target_group.structures.values()) if target_group else set()
            candidates.intersection_update(group_hashes)

        return candidates
