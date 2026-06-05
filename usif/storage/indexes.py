"""Index bookkeeping for USIF structure containers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, List, Tuple

from usif.format.hashing import calculate_geometry_hash
from usif.properties.values import is_property_value_dict, normalize_json_value
from usif.structures.structure import USIFStructure


def make_index_key(value: Any) -> Hashable:
    """Return a hashable, JSON-normalized key for secondary indexes.

    Structure properties may be scalars, vectors, tensors, or JSON-compatible
    custom values.  Query indexes need hashable keys, so list-like values are
    recursively represented as tuples while scalar values keep their natural
    Python type.  Dictionaries are intentionally not used as direct keys; their
    scalar/vector/tensor leaves are indexed under dotted paths instead.
    """
    normalized = normalize_json_value(value)
    if isinstance(normalized, list):
        return tuple(make_index_key(item) for item in normalized)
    if isinstance(normalized, dict):
        raise TypeError("dictionary values must be indexed through dotted leaves")
    return normalized


def is_indexable_value(value: Any) -> bool:
    """Return True when a property value can be used as an index bucket key."""
    try:
        make_index_key(value)
        return True
    except (TypeError, ValueError):
        return False


def iter_indexable_properties(prefix: str, value: Any):
    """Yield ``(dotted_property_name, key)`` pairs for query indexes.

    Scalars, vectors, and tensors are indexed directly.  Dictionaries are
    recursively indexed by dotted leaf path, which keeps custom metadata useful
    for queries without requiring dictionaries to become hash keys.
    """
    normalized = normalize_json_value(value)
    if is_property_value_dict(normalized):
        yield from iter_indexable_properties(prefix, normalized.get("value"))
        if isinstance(normalized.get("units"), str):
            yield from iter_indexable_properties(f"{prefix}.units", normalized["units"])
        return
    if isinstance(normalized, dict):
        for sub_key, sub_value in normalized.items():
            yield from iter_indexable_properties(f"{prefix}.{sub_key}", sub_value)
        return
    try:
        yield prefix, make_index_key(normalized)
    except (TypeError, ValueError):
        return


@dataclass
class ContainerIndexes:
    """Primary and secondary indexes used by StructureContainer.

    ``record_index`` maps record hashes to chunk locations. ``geometry_index``
    maps a geometry hash to one or more record hashes.  Secondary indexes are
    persisted in current containers so opening a large container does not need
    to decode every record just to answer common queries.
    """

    record_index: Dict[str, Tuple[int, int, int]] = field(default_factory=dict)
    geometry_index: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    name_index: Dict[str, str] = field(default_factory=dict)
    formula_index: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    property_index: Dict[str, Dict[Hashable, List[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )
    group_index: Dict[str, Any] = field(default_factory=dict)
    structure_attributes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    secondary_indexes_complete: bool = False

    def clear_secondary(self) -> None:
        """Clear rebuildable secondary indexes."""
        self.geometry_index.clear()
        self.formula_index.clear()
        self.property_index.clear()
        self.secondary_indexes_complete = False

    def update_secondary(self, structure: USIFStructure, record_hash: str) -> None:
        """Update persisted query indexes for one structure."""
        geometry_hash = calculate_geometry_hash(structure).hex()
        if record_hash not in self.geometry_index[geometry_hash]:
            self.geometry_index[geometry_hash].append(record_hash)

        if record_hash not in self.formula_index[structure.formula]:
            self.formula_index[structure.formula].append(record_hash)

        for prop_name, value in structure.structure_properties.get_all_properties().items():
            for index_name, key in iter_indexable_properties(prop_name, value):
                if record_hash not in self.property_index[index_name][key]:
                    self.property_index[index_name][key].append(record_hash)

        self.secondary_indexes_complete = True
