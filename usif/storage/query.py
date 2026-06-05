"""Query helpers for USIF containers."""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

from usif.constants import QueryConstants
from usif.storage.indexes import make_index_key


class QueryEngine:
    """Resolve container query filters against persisted secondary indexes."""

    def __init__(self, indexes, group_getter):
        self.indexes = indexes
        self.group_getter = group_getter

    def candidate_hashes(
        self,
        formula: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        energy_range: Optional[Tuple[float, float]] = None,
        group: Optional[str] = None,
        numeric_tolerance: float = QueryConstants.DEFAULT_NUMERIC_TOLERANCE,
        has_property: Optional[str] = None,
        property_range: Optional[Tuple[str, float, float]] = None,
        custom: Optional[Dict[str, Any]] = None,
    ) -> Set[str]:
        if formula:
            candidates = set(self.indexes.formula_index.get(formula, []))
        else:
            candidates = set(self.indexes.record_index.keys())

        merged_properties: Dict[str, Any] = {}
        if properties:
            merged_properties.update(properties)
        if custom:
            merged_properties.update(custom)

        if merged_properties:
            for prop_name, prop_value in merged_properties.items():
                prop_index = self.indexes.property_index.get(prop_name)
                if not prop_index:
                    candidates.clear()
                    break
                if isinstance(prop_value, (int, float)) and not isinstance(prop_value, bool):
                    matches = set()
                    for bucket, hashes in prop_index.items():
                        if (
                            isinstance(bucket, (int, float))
                            and not isinstance(bucket, bool)
                            and abs(bucket - prop_value) <= numeric_tolerance
                        ):
                            matches.update(hashes)
                    candidates.intersection_update(matches)
                else:
                    try:
                        key = make_index_key(prop_value)
                    except (TypeError, ValueError):
                        candidates.clear()
                        break
                    candidates.intersection_update(prop_index.get(key, []))

        if has_property:
            prop_index = self.indexes.property_index.get(has_property, {})
            prop_hashes = {item for hashes in prop_index.values() for item in hashes}
            candidates.intersection_update(prop_hashes)

        if property_range:
            prop_name, min_value, max_value = property_range
            range_hashes = set()
            for bucket, hashes in self.indexes.property_index.get(prop_name, {}).items():
                if (
                    isinstance(bucket, (int, float))
                    and not isinstance(bucket, bool)
                    and min_value <= bucket <= max_value
                ):
                    range_hashes.update(hashes)
            candidates.intersection_update(range_hashes)

        if energy_range:
            min_energy, max_energy = energy_range
            energy_hashes = set()
            for bucket, hashes in self.indexes.property_index.get("energy", {}).items():
                if (
                    isinstance(bucket, (int, float))
                    and not isinstance(bucket, bool)
                    and min_energy <= bucket <= max_energy
                ):
                    energy_hashes.update(hashes)
            candidates.intersection_update(energy_hashes)

        if group and group != "/":
            target_group = self.group_getter(group)
            group_hashes = set(target_group.structures.values()) if target_group else set()
            candidates.intersection_update(group_hashes)

        return candidates
