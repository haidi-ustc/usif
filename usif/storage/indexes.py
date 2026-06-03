"""Index bookkeeping for USIF structure containers."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from usif.structures.structure import USIFStructure


@dataclass
class ContainerIndexes:
    """Primary and secondary indexes used by StructureContainer."""

    hash_index: Dict[str, Tuple[int, int, int]] = field(default_factory=dict)
    name_index: Dict[str, str] = field(default_factory=dict)
    formula_index: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    property_index: Dict[str, Dict[Any, List[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )
    group_index: Dict[str, Any] = field(default_factory=dict)
    structure_attributes: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def update_secondary(self, structure: USIFStructure, struct_hash: str) -> None:
        self.formula_index[structure.formula].append(struct_hash)

        props = structure.structure_properties.get_all_properties()
        for prop_name, value in props.items():
            if isinstance(value, (int, float)):
                bucket = round(value, 3)
                self.property_index[prop_name][bucket].append(struct_hash)
            elif isinstance(value, (str, bool, tuple)):
                self.property_index[prop_name][value].append(struct_hash)
            elif isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    if isinstance(sub_val, (int, float, str, bool)):
                        composite_key = f"{prop_name}.{sub_key}"
                        bucket = round(sub_val, 3) if isinstance(sub_val, float) else sub_val
                        self.property_index[composite_key][bucket].append(struct_hash)
            # Unhashable or unsupported types (list, set, complex objects) are skipped
