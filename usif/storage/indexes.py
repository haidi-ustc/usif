"""Index bookkeeping for USIF structure containers."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from usif.format.hashing import calculate_geometry_hash
from usif.structures.structure import USIFStructure


@dataclass
class ContainerIndexes:
    """Primary and secondary indexes used by StructureContainer.

    ``record_index`` maps record hashes to chunk locations. ``geometry_index``
    maps a geometry hash to one or more record hashes.
    """

    record_index: Dict[str, Tuple[int, int, int]] = field(default_factory=dict)
    geometry_index: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    name_index: Dict[str, str] = field(default_factory=dict)
    formula_index: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    property_index: Dict[str, Dict[Any, List[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )
    group_index: Dict[str, Any] = field(default_factory=dict)
    structure_attributes: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def clear_secondary(self) -> None:
        """Clear rebuildable secondary indexes."""
        self.geometry_index.clear()
        self.formula_index.clear()
        self.property_index.clear()

    def update_secondary(self, structure: USIFStructure, record_hash: str) -> None:
        geometry_hash = calculate_geometry_hash(structure).hex()
        if record_hash not in self.geometry_index[geometry_hash]:
            self.geometry_index[geometry_hash].append(record_hash)

        if record_hash not in self.formula_index[structure.formula]:
            self.formula_index[structure.formula].append(record_hash)

        props = structure.structure_properties.get_all_properties()
        for prop_name, value in props.items():
            if isinstance(value, (int, float, str, bool, tuple)):
                if record_hash not in self.property_index[prop_name][value]:
                    self.property_index[prop_name][value].append(record_hash)
            elif isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    if isinstance(sub_val, (int, float, str, bool, tuple)):
                        composite_key = f"{prop_name}.{sub_key}"
                        if record_hash not in self.property_index[composite_key][sub_val]:
                            self.property_index[composite_key][sub_val].append(record_hash)
            # Unhashable or unsupported types (list, set, complex objects) are skipped
