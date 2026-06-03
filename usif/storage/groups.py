"""Group hierarchy model for USIF containers."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class USIFGroup:
    """HDF5-like group for organizing structures and metadata."""

    name: str
    structures: Dict[str, str] = field(default_factory=dict)
    subgroups: Dict[str, "USIFGroup"] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def add_structure(self, name: str, struct_hash: str) -> None:
        self.structures[name] = struct_hash

    def remove_structure(self, name: str) -> bool:
        if name in self.structures:
            del self.structures[name]
            return True
        return False

    def get_subgroup(self, path: str) -> Optional["USIFGroup"]:
        if not path or path == "/":
            return self

        parts = [p for p in path.split("/") if p]
        current = self

        for part in parts:
            if part in current.subgroups:
                current = current.subgroups[part]
            else:
                return None

        return current

    def list_structures(self) -> List[str]:
        return list(self.structures.keys())

    def list_subgroups(self) -> List[str]:
        return list(self.subgroups.keys())

    def set_attribute(self, name: str, value: Any) -> None:
        self.attributes[name] = value

    def get_attribute(self, name: str, default: Any = None) -> Any:
        return self.attributes.get(name, default)

    def has_attribute(self, name: str) -> bool:
        return name in self.attributes
