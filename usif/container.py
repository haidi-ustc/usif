#!/usr/bin/env python3
"""
USIF Structure Container Module

This module provides a container system for storing and managing multiple USIF structures
with HDF5-like hierarchical organization, indexing, and efficient storage.

Main Classes:
    StructureContainer: Container for multiple structures with indexing
    USIFGroup: HDF5-like group for hierarchical organization

Features:
    - Store multiple structures in a single file
    - HDF5-like hierarchical groups and attributes
    - Indexing by formula, spacegroup, properties
    - Thread-safe operations
    - Efficient storage with deduplication
    - Query and filter structures

Usage:
    >>> from usif import StructureContainer, USIFStructure
    >>>
    >>> # Create container
    >>> container = StructureContainer('structures.usifc')
    >>>
    >>> # Add structures
    >>> container.add('structure1', structure1)
    >>> container.add('structure2', structure2)
    >>>
    >>> # Organize in groups
    >>> container.create_group('crystals')
    >>> container.add('crystals/NaCl', nacl_structure)
    >>>
    >>> # Query structures
    >>> results = container.query(formula='NaCl', energy_max=-10.0)
    >>>
    >>> # Get structure
    >>> structure = container.get('structure1')
    >>>
    >>> # Save and close
    >>> container.close()

See Also:
    - USIFStructure: Individual structure representation
    - USIFGroup: Group organization
"""

import logging
import mmap
import queue
import struct
import threading
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from usif.constants import BinaryFormat, SymmetryConstants
from usif.encoder import USIF
from usif.constants import CompressionType
from usif.exceptions import (
    CorruptedDataError,
    DecodingError,
    StorageError,
    ValidationError,
)
from usif.structures.structure import USIFStructure

logger = logging.getLogger(__name__)


@dataclass
class USIFGroup:
    """
    Group for organizing structures (HDF5-like hierarchical organization)

    Groups can contain structures and subgroups, similar to HDF5 groups.
    Supports attributes for metadata storage.
    """

    name: str
    structures: Dict[str, str] = field(default_factory=dict)
    subgroups: Dict[str, "USIFGroup"] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def add_structure(self, name: str, struct_hash: str) -> None:
        """Add structure to group"""
        self.structures[name] = struct_hash

    def remove_structure(self, name: str) -> bool:
        """Remove structure from group"""
        if name in self.structures:
            del self.structures[name]
            return True
        return False

    def get_subgroup(self, path: str) -> Optional["USIFGroup"]:
        """Get subgroup by path (HDF5-like path navigation)"""
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
        """List all structure names in this group"""
        return list(self.structures.keys())

    def list_subgroups(self) -> List[str]:
        """List all subgroup names"""
        return list(self.subgroups.keys())

    def set_attribute(self, name: str, value: Any) -> None:
        """Set group attribute (HDF5-like attributes)"""
        self.attributes[name] = value

    def get_attribute(self, name: str, default: Any = None) -> Any:
        """Get group attribute"""
        return self.attributes.get(name, default)

    def has_attribute(self, name: str) -> bool:
        """Check if group has attribute"""
        return name in self.attributes


class StructureContainer:
    """
    Container for storing multiple USIF structures with indexing
    Thread-safe implementation with proper error handling
    """

    CONTAINER_MAGIC = b"USIFC\x00\x00"
    CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB chunks

    def __init__(
        self,
        filename: Union[str, Path],
        mode: str = "r",
        compression: CompressionType = CompressionType.GZIP,
        use_mmap: bool = True,
        cache_size: int = 1000,
        num_workers: int = 4,
    ):
        """
        Initialize container

        Args:
            filename: Container file path
            mode: Open mode ('r', 'w', 'a')
            compression: Compression type
            use_mmap: Use memory mapping
            cache_size: Cache size
            num_workers: Number of worker threads
        """
        if mode not in ("r", "w", "a"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'r', 'w', or 'a'")

        self.filename = Path(filename).resolve()
        self.mode = mode
        self.encoder = USIF(compression=compression)
        self.use_mmap = use_mmap
        self.num_workers = max(1, min(num_workers, 32))

        # Thread-safe cache
        self._cache = OrderedDict()
        self._cache_lock = threading.RLock()
        self._cache_size = cache_size

        # Indexes with thread-safe lock
        self._index_lock = threading.RLock()  # NEW: Lock for index operations
        self._file_lock = threading.RLock()  # NEW: Lock for file I/O operations
        self._hash_index: Dict[str, Tuple[int, int, int]] = {}
        self._name_index: Dict[str, str] = {}
        self._formula_index: Dict[str, List[str]] = defaultdict(list)
        self._property_index: Dict[str, Dict[Any, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._group_index: Dict[str, USIFGroup] = {}
        self._structure_attributes: Dict[str, Dict[str, Any]] = (
            {}
        )  # HDF5-like attributes

        # File and mmap
        self._file = None
        self._mmap = None

        # Group hierarchy
        self.root_group = USIFGroup("/")

        # Prefetch queue
        self._prefetch_queue = queue.Queue()
        self._prefetch_thread = None

        # Data offsets
        self._data_offset = self.HEADER_SIZE = 64
        self._index_offset = 0

        # Initialize
        if mode == "r":
            if not self.filename.exists():
                raise FileNotFoundError(f"File not found: {self.filename}")
            self._file = open(self.filename, "rb")
            if use_mmap:
                try:
                    self._mmap = mmap.mmap(
                        self._file.fileno(), 0, access=mmap.ACCESS_READ
                    )
                except Exception as e:
                    logger.warning(f"Failed to create mmap: {e}")
                    self.use_mmap = False
            self._read_enhanced_index()
        elif mode in ["w", "a"]:
            if mode == "a" and self.filename.exists():
                self._file = open(self.filename, "r+b")
                if use_mmap:
                    try:
                        self._mmap = mmap.mmap(self._file.fileno(), 0)
                    except Exception as e:
                        logger.warning(f"Failed to create mmap: {e}")
                        self.use_mmap = False
                self._read_enhanced_index()
            else:
                # Use w+b to allow both writing and reading
                # Don't use mmap for new files (file is initially empty)
                self._file = open(self.filename, "w+b")
                self.use_mmap = False  # Disable mmap for new write mode
                self._write_header()

        # Start prefetch thread
        if self._prefetch_queue and num_workers > 0:
            self._start_prefetch_thread()

    def _write_header(self) -> None:
        """Write container header"""
        header = bytearray(self.HEADER_SIZE)
        header[0:7] = self.CONTAINER_MAGIC
        header[7:8] = struct.pack(BinaryFormat.UINT8, 1)  # Version
        header[8:12] = struct.pack(BinaryFormat.UINT32, 0)  # num_structures
        header[12:20] = struct.pack(
            BinaryFormat.UINT64, self.HEADER_SIZE
        )  # data_offset
        header[20:28] = struct.pack(BinaryFormat.UINT64, 0)  # index_offset
        header[28:36] = struct.pack(BinaryFormat.UINT64, 0)  # group_offset
        header[36:44] = struct.pack(BinaryFormat.UINT64, 0)  # attribute_offset
        header[44:45] = struct.pack(BinaryFormat.UINT8, self.encoder.compression.value)
        header[45:46] = struct.pack(BinaryFormat.UINT8, 1)  # use_chunking

        import time

        timestamp = int(time.time())
        header[46:54] = struct.pack(BinaryFormat.UINT64, timestamp)
        header[54:62] = struct.pack(BinaryFormat.UINT64, timestamp)

        self._file.write(header)
        self._file.flush()

    def _read_enhanced_index(self) -> None:
        """Read enhanced index with secondary indexes (FIXED: matches new serialization format)"""
        try:
            if self._mmap:
                data = self._mmap
            else:
                self._file.seek(0)
                data = self._file.read()

            magic = data[0:7]
            if magic != self.CONTAINER_MAGIC:
                # Check if it's a single structure file instead
                if magic == b"USIF\x00\x00\x00":
                    raise StorageError(
                        f"File {self.filename} is a USIF structure file, not a container. "
                        f"Use USIFStructure.load() to open it."
                    )
                raise CorruptedDataError("Invalid enhanced USIF container")

            struct.unpack(BinaryFormat.UINT8, data[7:8])[0]  # version
            struct.unpack(BinaryFormat.UINT32, data[8:12])[0]  # num_structures
            data_offset = struct.unpack(BinaryFormat.UINT64, data[12:20])[0]
            index_offset = struct.unpack(BinaryFormat.UINT64, data[20:28])[0]
            struct.unpack(BinaryFormat.UINT64, data[28:36])[0]  # group_offset

            self._data_offset = data_offset
            self._index_offset = index_offset

            # FIXED: Read new serialization format
            if index_offset > 0 and index_offset < len(data):
                self._file.seek(index_offset)
                self._deserialize_indexes()

            self._build_secondary_indexes()

        except Exception as e:
            logger.error(f"Failed to read index: {e}")
            raise StorageError(f"Failed to read container index: {e}") from e

    def _read_group_hierarchy(self, group_offset: int) -> None:
        """Read group hierarchy from file"""
        try:
            self._file.seek(group_offset)

            num_groups = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]

            for _ in range(num_groups):
                name_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
                name = self._file.read(name_len).decode("utf-8")

                num_structures = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[
                    0
                ]
                group = self.create_group(name)

                for _ in range(num_structures):
                    struct_name_len = struct.unpack(
                        BinaryFormat.UINT16, self._file.read(2)
                    )[0]
                    struct_name = self._file.read(struct_name_len).decode("utf-8")
                    hash_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
                    struct_hash = self._file.read(hash_len).decode("utf-8")

                    group.add_structure(struct_name, struct_hash)
                    self._name_index[struct_name] = struct_hash
        except Exception as e:
            logger.error(f"Failed to read group hierarchy: {e}")

    def _build_secondary_indexes(self) -> None:
        """Build secondary indexes for fast querying (thread-safe, all structures)"""
        logger.info("Building secondary indexes...")

        # FIXED: Index all structures, not just first 10
        all_hashes = list(self._hash_index.keys())
        total = len(all_hashes)

        with self._index_lock:  # FIXED: Thread-safe index building
            for i, struct_hash in enumerate(all_hashes):
                try:
                    structure = self.get(struct_hash)
                    if structure:
                        self._formula_index[structure.formula].append(struct_hash)

                        props = structure.structure_properties.get_all_properties()
                        for prop_name, value in props.items():
                            if isinstance(value, (int, float)):
                                bucket = round(value, 3)
                                self._property_index[prop_name][bucket].append(
                                    struct_hash
                                )
                            else:
                                self._property_index[prop_name][value].append(
                                    struct_hash
                                )

                    # Log progress for large containers
                    if (i + 1) % 100 == 0:
                        logger.info(f"Indexed {i + 1}/{total} structures...")

                except Exception as e:
                    logger.warning(f"Failed to index structure {struct_hash[:16]}: {e}")

        logger.info(f"Secondary indexing complete: {total} structures indexed")

    def _start_prefetch_thread(self) -> None:
        """Start background thread for prefetching"""

        def prefetch_worker():
            while True:
                try:
                    hashes = self._prefetch_queue.get(timeout=1.0)
                    if hashes is None:
                        break
                    for h in hashes:
                        with self._cache_lock:
                            if h not in self._cache:
                                self.get(h)
                    self._prefetch_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Prefetch error: {e}")

        self._prefetch_thread = threading.Thread(target=prefetch_worker, daemon=True)
        self._prefetch_thread.start()

    def add(
        self,
        structure: USIFStructure,
        name: Optional[str] = None,
        group: str = "/",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add structure to container with optional naming and grouping

        Adds a USIFStructure to the container with HDF5-like hierarchical organization.
        Structures can be organized in groups and have associated attributes/metadata.
        Duplicate structures (same hash) are automatically detected and not stored twice.

        Args:
            structure: USIFStructure instance to add
            name: Optional name for the structure (for retrieval by name)
            group: Group path for hierarchical organization (default: "/" for root)
            attributes: Optional dictionary of attributes/metadata (HDF5-like)

        Returns:
            str: Structure hash (unique identifier)

        Raises:
            ValueError: If container is opened in read-only mode
            ValidationError: If structure is invalid
            StorageError: If storage operation fails

        Example:
            >>> container = StructureContainer("structures.usifc", mode="w")
            >>> structure = USIFStructure(...)
            >>> hash_id = container.add(
            ...     structure,
            ...     name="NaCl_001",
            ...     group="/crystals/NaCl",
            ...     attributes={"temperature": 300, "pressure": 0.0}
            ... )
        """
        if self.mode == "r":
            raise ValueError("Cannot add to read-only container")

        if not isinstance(structure, USIFStructure):
            raise ValidationError(
                f"Expected USIFStructure, got {type(structure).__name__}"
            )

        try:
            usif_data = self.encoder.encode(structure)
            struct_hash = self.encoder.get_structure_hash(structure)

            # FIXED: Thread-safe check and index updates
            with self._index_lock:
                if struct_hash in self._hash_index:
                    logger.info(f"Structure {struct_hash[:16]} already exists")
                    return struct_hash

            # FIXED: Thread-safe file I/O operations
            with self._file_lock:
                chunk_id, chunk_offset = self._allocate_space(len(usif_data))
                self._write_to_chunk(chunk_id, chunk_offset, usif_data)

            with self._index_lock:
                self._hash_index[struct_hash] = (chunk_id, chunk_offset, len(usif_data))

                if name:
                    self._name_index[name] = struct_hash
                    # Store attributes if provided (HDF5-like attributes)
                    if attributes:
                        self._structure_attributes[name] = attributes

                target_group = self._get_or_create_group(group)
                display_name = name or struct_hash[:16]
                target_group.add_structure(display_name, struct_hash)

            self._update_secondary_indexes(structure, struct_hash)

            logger.debug(f"Added structure {struct_hash[:16]} (name: {name or 'N/A'})")

            return struct_hash

        except Exception as e:
            logger.error(f"Failed to add structure: {e}")
            raise StorageError(f"Failed to add structure: {e}") from e

    def add_structure(
        self,
        structure: USIFStructure,
        name: Optional[str] = None,
        group: str = "/",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add structure to container (alias for add, more explicit name)

        This method provides a more intuitive name for adding structures,
        similar to HDF5 dataset creation.

        Args:
            structure: USIF structure to add
            name: Optional name for the structure
            group: Group path (default is root)
            attributes: Optional attributes/metadata for the structure

        Returns:
            Structure hash
        """
        return self.add(structure, name=name, group=group, attributes=attributes)

    def _allocate_space(self, size: int) -> Tuple[int, int]:
        """Allocate space in chunked storage"""
        if self._mmap:
            current_pos = self._mmap.size()
        else:
            self._file.seek(0, 2)  # Seek to end
            current_pos = self._file.tell()

        chunk_id = current_pos // self.CHUNK_SIZE
        chunk_offset = current_pos % self.CHUNK_SIZE

        if chunk_offset + size > self.CHUNK_SIZE:
            chunk_id += 1
            chunk_offset = 0
            if self._mmap:
                self._mmap.resize(chunk_id * self.CHUNK_SIZE)
            else:
                # Pad to the start of next chunk
                padding_size = self.CHUNK_SIZE - (current_pos % self.CHUNK_SIZE)
                if padding_size > 0:
                    self._file.write(b"\x00" * padding_size)
                    self._file.flush()

        return chunk_id, chunk_offset

    def _write_to_chunk(self, chunk_id: int, offset: int, data: bytes) -> None:
        """Write data to specific chunk"""
        actual_offset = chunk_id * self.CHUNK_SIZE + offset

        if self._mmap:
            required_size = actual_offset + len(data)
            if required_size > self._mmap.size():
                self._mmap.resize(required_size)
            self._mmap[actual_offset : actual_offset + len(data)] = data
            self._mmap.flush()  # Ensure data is written
        else:
            # Get current file size
            self._file.seek(0, 2)
            file_size = self._file.tell()

            # If we need to write beyond current file size, extend the file
            required_size = actual_offset + len(data)
            if required_size > file_size:
                # Pad with zeros if there's a gap
                if actual_offset > file_size:
                    self._file.write(b"\x00" * (actual_offset - file_size))

            # Write the data
            self._file.seek(actual_offset)
            self._file.write(data)
            self._file.flush()  # Ensure data is flushed to disk

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

    def _update_secondary_indexes(
        self, structure: USIFStructure, struct_hash: str
    ) -> None:
        """Update secondary indexes for a structure (thread-safe)"""
        with self._index_lock:  # FIXED: Thread-safe index updates
            self._formula_index[structure.formula].append(struct_hash)

            props = structure.structure_properties.get_all_properties()
            for prop_name, value in props.items():
                if isinstance(value, (int, float)):
                    bucket = round(value, 3)
                    self._property_index[prop_name][bucket].append(struct_hash)
                else:
                    self._property_index[prop_name][value].append(struct_hash)

    def get(self, identifier: str) -> Optional[USIFStructure]:
        """
        Get structure by hash or name (thread-safe)

        Retrieves a structure from the container using either its hash (unique ID)
        or its assigned name. Uses thread-safe caching for performance.

        Args:
            identifier: Structure hash (hex string) or assigned name

        Returns:
            USIFStructure if found, None otherwise

        Example:
            >>> container = StructureContainer("structures.usifc", mode="r")
            >>> # Get by name
            >>> structure = container.get("NaCl_001")
            >>> # Get by hash
            >>> structure = container.get("a1b2c3d4e5f6...")
        """
        with self._cache_lock:
            if identifier in self._cache:
                self._cache.move_to_end(identifier)
                return self._cache[identifier]

        # FIXED: Thread-safe index lookups
        with self._index_lock:
            struct_hash = self._name_index.get(identifier, identifier)

            if struct_hash not in self._hash_index:
                return None

            chunk_id, chunk_offset, size = self._hash_index[struct_hash]
        usif_data = self._read_from_chunk(chunk_id, chunk_offset, size)

        try:
            structure, _ = self.encoder.decode(usif_data)

            with self._cache_lock:
                self._cache[identifier] = structure
                if len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)

            return structure

        except (DecodingError, CorruptedDataError) as e:
            logger.error(f"Error decoding structure {identifier}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error decoding structure {identifier}: {e}", exc_info=True
            )
            return None

    def _read_from_chunk(self, chunk_id: int, offset: int, size: int) -> bytes:
        """Read data from specific chunk (thread-safe)"""
        actual_offset = chunk_id * self.CHUNK_SIZE + offset

        # FIXED: Thread-safe file I/O
        with self._file_lock:
            if self._mmap:
                return bytes(self._mmap[actual_offset : actual_offset + size])
            else:
                current_pos = self._file.tell()
                self._file.seek(actual_offset)
                data = self._file.read(size)
                self._file.seek(current_pos)
                return data

    def query(
        self,
        formula: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        energy_range: Optional[Tuple[float, float]] = None,
        group: Optional[str] = None,
    ) -> List[Tuple[str, USIFStructure]]:
        """
        Query structures with multiple criteria

        Searches the container for structures matching the specified criteria.
        All criteria are combined with AND logic (structures must match all).
        Uses efficient secondary indexes for fast querying.

        Args:
            formula: Chemical formula to match (e.g., "NaCl", "H2O")
            properties: Dictionary of property filters (e.g., {"pressure": 0.0})
            energy_range: Tuple of (min_energy, max_energy) in eV
            group: Group path to search within (e.g., "/crystals/NaCl")

        Returns:
            List[Tuple[str, USIFStructure]]: List of (hash, structure) tuples matching criteria

        Example:
            >>> # Find all NaCl structures
            >>> results = container.query(formula="NaCl")
            >>>
            >>> # Find structures with specific energy range
            >>> results = container.query(energy_range=(-10.0, -5.0))
            >>>
            >>> # Complex query
            >>> results = container.query(
            ...     formula="NaCl",
            ...     energy_range=(-10.0, -5.0),
            ...     properties={"pressure": 0.0},
            ...     group="/crystals"
            ... )
        """
        results = []

        # FIXED: Thread-safe query operations
        with self._index_lock:
            candidate_hashes = set()
            if formula:
                candidate_hashes.update(self._formula_index.get(formula, []))
            else:
                candidate_hashes.update(self._hash_index.keys())

            if properties:
                for prop_name, prop_value in properties.items():
                    if prop_name in self._property_index:
                        if isinstance(prop_value, (int, float)):
                            for bucket, hashes in self._property_index[
                                prop_name
                            ].items():
                                if (
                                    isinstance(bucket, (int, float))
                                    and abs(bucket - prop_value)
                                    < SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE
                                ):
                                    candidate_hashes.intersection_update(hashes)
                        else:
                            if prop_value in self._property_index[prop_name]:
                                candidate_hashes.intersection_update(
                                    self._property_index[prop_name][prop_value]
                                )

            if energy_range:
                min_energy, max_energy = energy_range
                energy_hashes = set()
                for bucket, hashes in self._property_index.get("energy", {}).items():
                    if (
                        isinstance(bucket, (int, float))
                        and min_energy <= bucket <= max_energy
                    ):
                        energy_hashes.update(hashes)
                candidate_hashes.intersection_update(energy_hashes)

            if group and group != "/":
                group_hashes = set()
                target_group = self.get_group(group)
                if target_group:
                    for struct_name, struct_hash in target_group.structures.items():
                        group_hashes.add(struct_hash)
                candidate_hashes.intersection_update(group_hashes)

        for hash_val in candidate_hashes:
            structure = self.get(hash_val)
            if structure:
                results.append((hash_val, structure))

        return results

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
        if name not in self._name_index:
            raise ValueError(f"Structure '{name}' not found")
        self._structure_attributes[name] = attributes

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

    def prefetch(self, identifiers: List[str]) -> None:
        """
        Prefetch structures for faster access

        Queues structures for background loading to improve subsequent access
        performance. Useful when you know which structures will be accessed next.

        Args:
            identifiers: List of structure identifiers (hashes or names) to prefetch

        Example:
            >>> container.prefetch(["NaCl_001", "NaCl_002", "NaCl_003"])
            >>> # Structures will be loaded in background
        """
        if self._prefetch_queue:
            self._prefetch_queue.put(identifiers)

    def get_batch_parallel(
        self, identifiers: List[str]
    ) -> List[Optional[USIFStructure]]:
        """
        Batch read using multiple threads (optimized)

        Retrieves multiple structures in parallel using thread pool execution.
        Much faster than sequential get() calls for large batches.

        Args:
            identifiers: List of structure identifiers (hashes or names)

        Returns:
            List[Optional[USIFStructure]]: List of structures in same order as identifiers
            (None for structures that couldn't be loaded)

        Example:
            >>> identifiers = ["NaCl_001", "NaCl_002", "NaCl_003"]
            >>> structures = container.get_batch_parallel(identifiers)
            >>> for ident, struct in zip(identifiers, structures):
            ...     if struct:
            ...         print(f"{ident}: {struct.formula}")
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not identifiers:
            return []

        ident_to_idx = {ident: idx for idx, ident in enumerate(identifiers)}
        results = [None] * len(identifiers)

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_ident = {
                executor.submit(self.get, ident): ident for ident in identifiers
            }

            for future in as_completed(future_to_ident):
                ident = future_to_ident[future]
                idx = ident_to_idx[ident]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Failed to get structure {ident}: {e}")
                    results[idx] = None

        return results

    def _write_enhanced_index(self) -> None:
        """Write enhanced index to file (persist indexes for HDF5-like functionality)"""
        if self.mode == "r" or not self._file:
            return

        try:
            # FIXED: Thread-safe index writing
            with self._file_lock:
                # Write index at the end of file
                index_data = self._serialize_indexes()
                self._file.seek(0, 2)  # FIXED: Seek to end of file first
                index_offset = self._file.tell()
                self._file.write(index_data)
                self._file.flush()

                # Update header with index offset
                self._file.seek(20)  # Index offset position in header
                self._file.write(struct.pack(BinaryFormat.UINT64, index_offset))
                self._file.flush()
        except Exception as e:
            logger.warning(f"Failed to write enhanced index: {e}")

    def _deserialize_indexes(self) -> None:
        """Deserialize indexes from file (matches _serialize_indexes format)"""
        # Read hash index
        num_hashes = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
        for _ in range(num_hashes):
            hash_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
            hash_bytes = self._file.read(hash_len)
            struct_hash = hash_bytes.decode("utf-8")
            chunk_id = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
            offset = struct.unpack(BinaryFormat.UINT64, self._file.read(8))[0]
            size = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
            self._hash_index[struct_hash] = (chunk_id, offset, size)

        # Read name index
        num_names = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
        for _ in range(num_names):
            name_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
            name = self._file.read(name_len).decode("utf-8")
            hash_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
            struct_hash = self._file.read(hash_len).decode("utf-8")
            self._name_index[name] = struct_hash

        # Read structure attributes
        num_attrs = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
        for _ in range(num_attrs):
            name_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
            name = self._file.read(name_len).decode("utf-8")
            num_attr_pairs = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
            attrs = {}
            for _ in range(num_attr_pairs):
                attr_name_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[
                    0
                ]
                attr_name = self._file.read(attr_name_len).decode("utf-8")
                value_len = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
                value_str = self._file.read(value_len).decode("utf-8")
                # Try to parse as number, otherwise keep as string
                try:
                    attrs[attr_name] = (
                        float(value_str) if "." in value_str else int(value_str)
                    )
                except ValueError:
                    attrs[attr_name] = value_str
            self._structure_attributes[name] = attrs

        # Read group hierarchy
        group_data_len = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
        if group_data_len > 0:
            group_data = self._file.read(group_data_len)
            self._deserialize_group_hierarchy(group_data)

    def _deserialize_group_hierarchy(self, data: bytes) -> None:
        """Deserialize group hierarchy from bytes"""

        def deserialize_group(
            offset: int, parent_path: str = "/"
        ) -> Tuple[USIFGroup, int]:
            # Group name
            name_len = struct.unpack(BinaryFormat.UINT16, data[offset : offset + 2])[0]
            offset += 2
            name = data[offset : offset + name_len].decode("utf-8")
            offset += name_len

            group = USIFGroup(name)

            # Calculate full path for this group
            if parent_path == "/":
                full_path = f"/{name}/" if name else "/"
            else:
                full_path = f"{parent_path}{name}/"

            # Add to group index (for stats and queries)
            if full_path != "/":
                self._group_index[full_path] = group

            # Structures in group
            num_structs = struct.unpack(BinaryFormat.UINT32, data[offset : offset + 4])[
                0
            ]
            offset += 4
            for _ in range(num_structs):
                struct_name_len = struct.unpack(
                    BinaryFormat.UINT16, data[offset : offset + 2]
                )[0]
                offset += 2
                struct_name = data[offset : offset + struct_name_len].decode("utf-8")
                offset += struct_name_len
                hash_len = struct.unpack(
                    BinaryFormat.UINT16, data[offset : offset + 2]
                )[0]
                offset += 2
                struct_hash = data[offset : offset + hash_len].decode("utf-8")
                offset += hash_len
                group.structures[struct_name] = struct_hash

            # Attributes
            num_attrs = struct.unpack(BinaryFormat.UINT16, data[offset : offset + 2])[0]
            offset += 2
            for _ in range(num_attrs):
                attr_name_len = struct.unpack(
                    BinaryFormat.UINT16, data[offset : offset + 2]
                )[0]
                offset += 2
                attr_name = data[offset : offset + attr_name_len].decode("utf-8")
                offset += attr_name_len
                value_len = struct.unpack(
                    BinaryFormat.UINT32, data[offset : offset + 4]
                )[0]
                offset += 4
                value_str = data[offset : offset + value_len].decode("utf-8")
                offset += value_len
                # Try to parse as number
                try:
                    group.attributes[attr_name] = (
                        float(value_str) if "." in value_str else int(value_str)
                    )
                except ValueError:
                    group.attributes[attr_name] = value_str

            # Subgroups
            num_subgroups = struct.unpack(
                BinaryFormat.UINT32, data[offset : offset + 4]
            )[0]
            offset += 4
            for _ in range(num_subgroups):
                subgroup, offset = deserialize_group(offset, full_path)
                group.subgroups[subgroup.name] = subgroup

            return group, offset

        self.root_group, _ = deserialize_group(0)

    def _serialize_indexes(self) -> bytes:
        """Serialize all indexes to bytes for persistence"""
        data = bytearray()

        # Serialize hash index
        data.extend(struct.pack(BinaryFormat.UINT32, len(self._hash_index)))
        for struct_hash, (chunk_id, offset, size) in self._hash_index.items():
            hash_bytes = struct_hash.encode("utf-8")
            data.extend(struct.pack(BinaryFormat.UINT16, len(hash_bytes)))
            data.extend(hash_bytes)
            data.extend(struct.pack(BinaryFormat.UINT32, chunk_id))
            data.extend(struct.pack(BinaryFormat.UINT64, offset))
            data.extend(struct.pack(BinaryFormat.UINT32, size))

        # Serialize name index
        data.extend(struct.pack(BinaryFormat.UINT32, len(self._name_index)))
        for name, struct_hash in self._name_index.items():
            name_bytes = name.encode("utf-8")
            data.extend(struct.pack(BinaryFormat.UINT16, len(name_bytes)))
            data.extend(name_bytes)
            hash_bytes = struct_hash.encode("utf-8")
            data.extend(struct.pack(BinaryFormat.UINT16, len(hash_bytes)))
            data.extend(hash_bytes)

        # Serialize structure attributes
        data.extend(struct.pack(BinaryFormat.UINT32, len(self._structure_attributes)))
        for name, attrs in self._structure_attributes.items():
            name_bytes = name.encode("utf-8")
            data.extend(struct.pack(BinaryFormat.UINT16, len(name_bytes)))
            data.extend(name_bytes)
            data.extend(struct.pack(BinaryFormat.UINT16, len(attrs)))
            for attr_name, attr_value in attrs.items():
                attr_name_bytes = attr_name.encode("utf-8")
                data.extend(struct.pack(BinaryFormat.UINT16, len(attr_name_bytes)))
                data.extend(attr_name_bytes)
                value_str = str(attr_value)
                value_bytes = value_str.encode("utf-8")
                data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
                data.extend(value_bytes)

        # Serialize group hierarchy
        group_data = self._serialize_group_hierarchy()
        data.extend(struct.pack(BinaryFormat.UINT32, len(group_data)))
        data.extend(group_data)

        return bytes(data)

    def _serialize_group_hierarchy(self) -> bytes:
        """Serialize group hierarchy to bytes (HDF5-like group structure)"""

        def serialize_group(group: USIFGroup) -> bytes:
            data = bytearray()

            # Group name
            name_bytes = group.name.encode("utf-8")
            data.extend(struct.pack(BinaryFormat.UINT16, len(name_bytes)))
            data.extend(name_bytes)

            # Structures in group
            data.extend(struct.pack(BinaryFormat.UINT32, len(group.structures)))
            for struct_name, struct_hash in group.structures.items():
                name_bytes = struct_name.encode("utf-8")
                data.extend(struct.pack(BinaryFormat.UINT16, len(name_bytes)))
                data.extend(name_bytes)
                hash_bytes = struct_hash.encode("utf-8")
                data.extend(struct.pack(BinaryFormat.UINT16, len(hash_bytes)))
                data.extend(hash_bytes)

            # Attributes
            data.extend(struct.pack(BinaryFormat.UINT16, len(group.attributes)))
            for attr_name, attr_value in group.attributes.items():
                name_bytes = attr_name.encode("utf-8")
                data.extend(struct.pack(BinaryFormat.UINT16, len(name_bytes)))
                data.extend(name_bytes)
                value_str = str(attr_value)
                value_bytes = value_str.encode("utf-8")
                data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
                data.extend(value_bytes)

            # Subgroups
            data.extend(struct.pack(BinaryFormat.UINT32, len(group.subgroups)))
            for subgroup in group.subgroups.values():
                data.extend(serialize_group(subgroup))

            return bytes(data)

        return serialize_group(self.root_group)

    def stats(self) -> Dict[str, Any]:
        """
        Get detailed container statistics

        Returns comprehensive statistics about the container including structure
        counts, sizes, index sizes, cache information, and configuration.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - total_structures: Number of structures in container
                - total_groups: Number of groups
                - total_size_bytes: Total size of all structures
                - average_structure_size: Average structure size in bytes
                - hash_index_size: Size of hash index
                - secondary_index_size: Size of secondary indexes
                - cache_size: Number of structures in cache
                - cache_hit_ratio: Cache hit ratio (currently 0.0)
                - compression_enabled: Whether compression is enabled
                - mmap_enabled: Whether memory mapping is enabled
                - chunk_size: Chunk size in bytes

        Example:
            >>> stats = container.stats()
            >>> print(f"Total structures: {stats['total_structures']}")
            >>> print(f"Total size: {stats['total_size_bytes'] / 1024 / 1024:.2f} MB")
        """
        total_structures = len(self._hash_index)
        total_groups = len(self._group_index)

        total_size = sum(size for _, _, size in self._hash_index.values())
        avg_size = total_size / total_structures if total_structures else 0

        hash_index_size = total_structures * 44
        secondary_index_size = sum(
            len(hashes) * 16 for hashes in self._formula_index.values()
        ) + sum(
            len(bucket_hashes) * 16
            for prop_dict in self._property_index.values()
            for bucket_hashes in prop_dict.values()
        )

        with self._cache_lock:
            cache_size = len(self._cache)

        return {
            "total_structures": total_structures,
            "total_groups": total_groups,
            "total_size_bytes": total_size,
            "average_structure_size": avg_size,
            "hash_index_size": hash_index_size,
            "secondary_index_size": secondary_index_size,
            "cache_size": cache_size,
            "cache_hit_ratio": 0.0,
            "compression_enabled": self.encoder.compression != CompressionType.NONE,
            "mmap_enabled": self.use_mmap,
            "chunk_size": self.CHUNK_SIZE,
        }

    def close(self) -> None:
        """
        Close container and cleanup resources

        Closes the container, writes indexes if in write mode, stops background
        threads, and releases file handles and memory mappings. Should be called
        when done with the container to ensure data is persisted and resources
        are freed.

        The container can also be used as a context manager (with statement),
        which automatically calls close().

        Example:
            >>> container = StructureContainer("structures.usifc", mode="w")
            >>> # ... use container ...
            >>> container.close()
            >>>
            >>> # Or use as context manager
            >>> with StructureContainer("structures.usifc", mode="r") as container:
            ...     structure = container.get("NaCl_001")
        """
        # Write indexes before closing if in write mode
        if self.mode in ("w", "a") and self._file:
            try:
                self._write_enhanced_index()
            except Exception as e:
                logger.warning(f"Failed to write index on close: {e}")

        if (
            hasattr(self, "_prefetch_thread")
            and self._prefetch_thread
            and self._prefetch_thread.is_alive()
        ):
            self._prefetch_queue.put(None)
            self._prefetch_thread.join(timeout=5.0)

        if self._mmap:
            self._mmap.close()
            self._mmap = None

        if self._file:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __len__(self):
        return len(self._hash_index)

    def __contains__(self, identifier: str):
        return identifier in self._hash_index or identifier in self._name_index

    def __iter__(self):
        for struct_hash in self._hash_index:
            structure = self.get(struct_hash)
            if structure:
                yield struct_hash, structure

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
