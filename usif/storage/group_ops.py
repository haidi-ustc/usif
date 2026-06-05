"""Group hierarchy and metadata operations for USIF containers."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Tuple

from usif.storage.groups import USIFGroup
from usif.structures.structure import USIFStructure


class GroupOperationsMixin:
    """HDF5-like group and attribute operations."""

    def _record_structure_metadata(
        self,
        struct_hash: str,
        name: Optional[str],
        group: str,
        attributes: Optional[Dict[str, Any]],
    ) -> None:
        """Record aliases, group membership, and attributes for a stored record."""
        if name:
            self._name_index[name] = struct_hash
            if attributes is not None:
                self._structure_attributes[name] = self._normalise_attributes(attributes)

        target_group = self._get_or_create_group(group)
        display_name = name or struct_hash[:16]
        target_group.add_structure(display_name, struct_hash)

    def _get_or_create_group(self, path: str) -> USIFGroup:
        """Get or create group by path"""
        if path == "/":
            return self.root_group

        parts = [p for p in path.split("/") if p]
        current = self.root_group

        full_path = "/"
        for part in parts:
            full_path += part + "/"
            if part not in current.subgroups:
                current.subgroups[part] = USIFGroup(part)
                self._group_index[full_path] = current.subgroups[part]
            current = current.subgroups[part]

        return current

    def get_group(self, path: str) -> Optional[USIFGroup]:
        """
        Get group by path (HDF5-like group access)

        Retrieves a group from the container's hierarchical organization.
        Groups can contain structures and subgroups, similar to HDF5 groups.

        Args:
            path: Group path (e.g., "/crystals/NaCl" or "/molecules")

        Returns:
            USIFGroup if found, None otherwise

        Example:
            >>> group = container.get_group("/crystals/NaCl")
            >>> if group:
            ...     structures = group.list_structures()
        """
        return self.root_group.get_subgroup(path)

    def create_group(self, path: str) -> USIFGroup:
        """
        Create group hierarchy (HDF5-like group creation)

        Creates a new group or returns existing group at the specified path.
        Parent groups are created automatically if they don't exist.

        Args:
            path: Group path (e.g., "/crystals/NaCl")

        Returns:
            USIFGroup: Created or existing group

        Raises:
            ValueError: If container is read-only

        Example:
            >>> container.create_group("/crystals/NaCl")
            >>> container.create_group("/molecules/H2O")
        """
        if self.mode == "r":
            raise ValueError("Cannot create groups in read-only container")
        return self._get_or_create_group(path)

    def set_structure_attributes(self, name: str, attributes: Dict[str, Any]) -> None:
        """
        Set attributes for a named structure (HDF5-like attributes)

        Attaches metadata attributes to a named structure, similar to HDF5
        dataset attributes. Useful for storing additional information like
        calculation parameters, timestamps, etc.

        Args:
            name: Structure name (must exist in container)
            attributes: Dictionary of attribute name-value pairs

        Raises:
            ValueError: If structure name not found

        Example:
            >>> container.set_structure_attributes("NaCl_001", {
            ...     "temperature": 300,
            ...     "pressure": 0.0,
            ...     "calculator": "VASP"
            ... })
        """
        if self.mode == "r":
            raise ValueError("Cannot set attributes in read-only container")
        if name not in self._name_index:
            raise ValueError(f"Structure '{name}' not found")
        self._structure_attributes[name] = self._normalise_attributes(attributes)

    def get_structure_attributes(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get attributes for a named structure (HDF5-like attributes)

        Retrieves metadata attributes associated with a named structure.

        Args:
            name: Structure name

        Returns:
            Dict of attributes if found, None otherwise

        Example:
            >>> attrs = container.get_structure_attributes("NaCl_001")
            >>> if attrs:
            ...     print(f"Temperature: {attrs.get('temperature')}")
        """
        return self._structure_attributes.get(name)

    def set_group_attribute(self, group_path: str, name: str, value: Any) -> None:
        """
        Set attribute on a group (HDF5-like group attributes)

        Attaches metadata attributes to a group, similar to HDF5 group attributes.

        Args:
            group_path: Path to group
            name: Attribute name
            value: Attribute value

        Raises:
            ValueError: If container is read-only

        Example:
            >>> container.set_group_attribute("/crystals", "description", "Crystal structures")
        """
        if self.mode == "r":
            raise ValueError("Cannot set attributes in read-only container")
        group = self._get_or_create_group(group_path)
        group.set_attribute(name, value)

    def get_group_attribute(
        self, group_path: str, name: str, default: Any = None
    ) -> Any:
        """
        Get attribute from a group (HDF5-like group attributes)

        Retrieves a metadata attribute from a group.

        Args:
            group_path: Path to group
            name: Attribute name
            default: Default value if attribute not found

        Returns:
            Attribute value or default

        Example:
            >>> desc = container.get_group_attribute("/crystals", "description", "N/A")
        """
        group = self.get_group(group_path)
        if group:
            return group.get_attribute(name, default)
        return default

    def walk_groups(self, group_path: str = "/") -> Iterator[Tuple[str, USIFGroup]]:
        """
        Walk through group hierarchy (HDF5-like walk functionality)

        Args:
            group_path: Starting group path

        Yields:
            Tuple of (path, group) for each group in hierarchy
        """
        group = self.get_group(group_path) if group_path != "/" else self.root_group
        if not group:
            return

        yield group_path, group

        for subgroup_name, subgroup in group.subgroups.items():
            if group_path == "/":
                new_path = f"/{subgroup_name}"
            else:
                new_path = f"{group_path}/{subgroup_name}"
            yield from self.walk_groups(new_path)

    def list_groups(self) -> List[str]:
        """List all groups in container"""
        return list(self._group_index.keys())

    def get_structures_in_group(
        self, group_path: str
    ) -> List[Tuple[str, USIFStructure]]:
        """Get all structures in a specific group"""
        group = self.get_group(group_path)
        if not group:
            return []

        results = []
        for name, struct_hash in group.structures.items():
            structure = self.get(struct_hash)
            if structure:
                results.append((name, structure))

        return results
