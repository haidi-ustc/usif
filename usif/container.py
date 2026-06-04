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
import os
import queue
import struct
import threading
import time
import zlib
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from usif.constants import BinaryFormat, CompressionType, SymmetryConstants
from usif.encoder import USIF
from usif.exceptions import (
    CorruptedDataError,
    DecodingError,
    StorageError,
    ContainerError,
    ContainerIndexError,
    ValidationError,
)
from usif.storage import ChunkedFileStore, ContainerIndexes, QueryEngine, USIFGroup
from usif.format.binary import BinaryReader
from usif.structures.structure import USIFStructure

logger = logging.getLogger(__name__)


class StructureContainer:
    """
    Container for storing multiple USIF structures with indexing
    Thread-safe implementation with proper error handling
    """

    CONTAINER_MAGIC = b"USIFC\x00\x00"
    INDEX_MAGIC = b"USIFIDX1"
    INDEX_COMMIT = b"USIFDONE"
    INDEX_HEADER_FORMAT = "<8sQQI4s"
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
        self._indexes = ContainerIndexes()
        self._hash_index = self._indexes.hash_index  # record_hash -> (chunk, offset, size)
        self._geometry_index = self._indexes.geometry_index
        self._name_index = self._indexes.name_index
        self._formula_index = self._indexes.formula_index
        self._property_index = self._indexes.property_index
        self._group_index = self._indexes.group_index
        self._structure_attributes = self._indexes.structure_attributes

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
        self._index_generation = 0

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
        """Read container header and load the newest valid index generation."""
        try:
            if self._mmap:
                data = bytes(self._mmap[:])
            else:
                self._file.seek(0)
                data = self._file.read()

            if len(data) < self.HEADER_SIZE:
                raise CorruptedDataError(
                    f"Container is too short: {len(data)} < {self.HEADER_SIZE}"
                )

            reader = BinaryReader(data[: self.HEADER_SIZE], context="USIF container header")
            magic = reader.read_bytes(7, "container magic")
            if magic != self.CONTAINER_MAGIC:
                if magic == b"USIF\x00\x00\x00":
                    raise StorageError(
                        f"File {self.filename} is a USIF structure file, not a container. "
                        f"Use USIFStructure.load() to open it."
                    )
                raise CorruptedDataError("Invalid enhanced USIF container")

            reader.read_u8("container version")
            reader.read_u32("structure count")
            data_offset = reader.read_u64("data offset")
            index_offset = reader.read_u64("index offset")
            reader.read_u64("group offset")

            self._data_offset = data_offset
            self._index_offset = index_offset

            if index_offset > 0:
                try:
                    self._deserialize_index_at(data, index_offset)
                except ContainerIndexError as e:
                    logger.warning("Header index generation is invalid: %s", e)
                    recovered = self._find_latest_valid_index_offset(data)
                    if recovered is None:
                        raise
                    logger.info("Recovered container index generation at offset %s", recovered)
                    self._deserialize_index_at(data, recovered)
                    self._index_offset = recovered

            self._build_secondary_indexes()

        except (StorageError, CorruptedDataError, ContainerIndexError):
            raise
        except Exception as e:
            logger.error(f"Failed to read index: {e}")
            raise StorageError(f"Failed to read container index: {e}") from e

    def _clear_loaded_indexes(self) -> None:
        """Clear index state before loading a persisted generation."""
        self._hash_index.clear()
        self._geometry_index.clear()
        self._name_index.clear()
        self._formula_index.clear()
        self._property_index.clear()
        self._group_index.clear()
        self._structure_attributes.clear()
        self.root_group = USIFGroup("/")
        with self._cache_lock:
            self._cache.clear()

    def _deserialize_index_at(self, data: bytes, offset: int) -> None:
        """Load either a checksummed P1 index block or legacy raw index payload."""
        if offset < self.HEADER_SIZE or offset >= len(data):
            raise ContainerIndexError(
                f"Index offset {offset} is outside container size {len(data)}"
            )

        if data[offset : offset + len(self.INDEX_MAGIC)] == self.INDEX_MAGIC:
            header_size = struct.calcsize(self.INDEX_HEADER_FORMAT)
            if offset + header_size > len(data):
                raise ContainerIndexError("Truncated index manifest header")
            magic, generation, payload_size, checksum, _reserved = struct.unpack(
                self.INDEX_HEADER_FORMAT, data[offset : offset + header_size]
            )
            if magic != self.INDEX_MAGIC:
                raise ContainerIndexError("Invalid index magic")
            payload_start = offset + header_size
            payload_end = payload_start + payload_size
            commit_end = payload_end + len(self.INDEX_COMMIT)
            if commit_end > len(data):
                raise ContainerIndexError("Truncated index payload or commit marker")
            if data[payload_end:commit_end] != self.INDEX_COMMIT:
                raise ContainerIndexError("Missing index commit marker")
            payload = data[payload_start:payload_end]
            actual_checksum = zlib.crc32(payload) & 0xFFFFFFFF
            if actual_checksum != checksum:
                raise ContainerIndexError(
                    f"Index checksum mismatch: header {checksum:#x}, actual {actual_checksum:#x}"
                )
            self._clear_loaded_indexes()
            try:
                self._deserialize_indexes_from_payload(payload, strict=True)
            except Exception as e:
                raise ContainerIndexError(f"Invalid index payload: {e}") from e
            self._index_generation = generation
            return

        # Legacy P0/v4 index payload: read to EOF and parse without checksum.
        payload = data[offset:]
        self._clear_loaded_indexes()
        try:
            self._deserialize_indexes_from_payload(payload, strict=False)
            self._index_generation = 0
        except Exception as e:
            raise ContainerIndexError(f"Failed to read legacy index payload: {e}") from e

    def _find_latest_valid_index_offset(self, data: bytes) -> Optional[int]:
        """Scan append-only index generations and return the newest valid offset."""
        best = None
        best_generation = -1
        search_from = self.HEADER_SIZE
        while True:
            offset = data.find(self.INDEX_MAGIC, search_from)
            if offset < 0:
                break
            try:
                header_size = struct.calcsize(self.INDEX_HEADER_FORMAT)
                magic, generation, payload_size, checksum, _reserved = struct.unpack(
                    self.INDEX_HEADER_FORMAT, data[offset : offset + header_size]
                )
                payload_start = offset + header_size
                payload_end = payload_start + payload_size
                commit_end = payload_end + len(self.INDEX_COMMIT)
                if magic == self.INDEX_MAGIC and commit_end <= len(data):
                    payload = data[payload_start:payload_end]
                    if (
                        data[payload_end:commit_end] == self.INDEX_COMMIT
                        and (zlib.crc32(payload) & 0xFFFFFFFF) == checksum
                        and generation > best_generation
                    ):
                        best = offset
                        best_generation = generation
            except Exception:
                pass
            search_from = offset + 1
        return best

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
        """Build secondary indexes for fast querying (thread-safe, all structures)."""
        logger.info("Building secondary indexes...")

        all_hashes = list(self._hash_index.keys())
        total = len(all_hashes)

        with self._index_lock:
            self._indexes.clear_secondary()

        for i, stored_hash in enumerate(all_hashes):
            try:
                structure = self.get(stored_hash)
                if structure:
                    record_hash = self.encoder.get_record_hash(structure)
                    if record_hash != stored_hash:
                        self._migrate_primary_hash(stored_hash, record_hash)
                    self._update_secondary_indexes(structure, record_hash)

                if (i + 1) % 100 == 0:
                    logger.info(f"Indexed {i + 1}/{total} structures...")

            except Exception as e:
                logger.warning(f"Failed to index structure {stored_hash[:16]}: {e}")

        logger.info(f"Secondary indexing complete: {total} structures indexed")

    def _migrate_primary_hash(self, old_hash: str, new_hash: str) -> None:
        """Migrate legacy geometry-hash keys to record-hash keys in memory."""
        with self._index_lock:
            if old_hash not in self._hash_index or new_hash in self._hash_index:
                return
            self._hash_index[new_hash] = self._hash_index.pop(old_hash)

            for name, value in list(self._name_index.items()):
                if value == old_hash:
                    self._name_index[name] = new_hash

            self._replace_group_hash(self.root_group, old_hash, new_hash)

    def _replace_group_hash(self, group: USIFGroup, old_hash: str, new_hash: str) -> None:
        for struct_name, value in list(group.structures.items()):
            if value == old_hash:
                group.structures[struct_name] = new_hash
        for subgroup in group.subgroups.values():
            self._replace_group_hash(subgroup, old_hash, new_hash)

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
        Duplicate records (same record hash, including properties) are automatically detected and not stored twice.

        Args:
            structure: USIFStructure instance to add
            name: Optional name for the structure (for retrieval by name)
            group: Group path for hierarchical organization (default: "/" for root)
            attributes: Optional dictionary of attributes/metadata (HDF5-like)

        Returns:
            str: Record hash (unique identifier including properties)

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
            struct_hash = self.encoder.get_record_hash(structure)

            # P1: close the check/write/update TOCTOU window.  The index lock
            # guards the record reservation; the file lock is acquired inside it so
            # a second thread cannot pass the duplicate check before this record is
            # fully indexed.
            with self._index_lock:
                if struct_hash in self._hash_index:
                    logger.info(f"Record {struct_hash[:16]} already exists")
                    return struct_hash

                with self._file_lock:
                    chunk_id, chunk_offset = self._allocate_space(len(usif_data))
                    self._write_to_chunk(chunk_id, chunk_offset, usif_data)

                self._hash_index[struct_hash] = (chunk_id, chunk_offset, len(usif_data))

                if name:
                    self._name_index[name] = struct_hash
                    # Store attributes if provided (HDF5-like attributes)
                    if attributes:
                        self._structure_attributes[name] = attributes

                target_group = self._get_or_create_group(group)
                display_name = name or struct_hash[:16]
                target_group.add_structure(display_name, struct_hash)
                self._indexes.update_secondary(structure, struct_hash)

            logger.debug(f"Added structure {struct_hash[:16]} (name: {name or 'N/A'})")

            return struct_hash

        except (StorageError, ContainerError, ValidationError):
            raise
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

    def _file_store(self) -> ChunkedFileStore:
        """Create a chunked storage adapter for current file handles."""
        return ChunkedFileStore(self._file, self._mmap, self.CHUNK_SIZE)

    def _allocate_space(self, size: int) -> Tuple[int, int]:
        """Allocate space in chunked storage."""
        return self._file_store().allocate(size)

    def _write_to_chunk(self, chunk_id: int, offset: int, data: bytes) -> None:
        """Write data to specific chunk."""
        self._file_store().write(chunk_id, offset, data)

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
        """Update secondary indexes for a structure (thread-safe)."""
        with self._index_lock:
            self._indexes.update_secondary(structure, struct_hash)

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
            raise StorageError(f"Failed to decode stored structure {identifier}: {e}") from e
        except Exception as e:
            logger.error(
                f"Unexpected error decoding structure {identifier}: {e}", exc_info=True
            )
            raise StorageError(f"Failed to decode stored structure {identifier}: {e}") from e

    def _read_from_chunk(self, chunk_id: int, offset: int, size: int) -> bytes:
        """Read data from specific chunk (thread-safe)."""
        with self._file_lock:
            return self._file_store().read(chunk_id, offset, size)

    def query(
        self,
        formula: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        energy_range: Optional[Tuple[float, float]] = None,
        group: Optional[str] = None,
        numeric_tolerance: float = SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE,
    ) -> List[Tuple[str, USIFStructure]]:
        """Query structures with multiple criteria."""
        with self._index_lock:
            query_engine = QueryEngine(self._indexes, self.get_group)
            candidate_hashes = query_engine.candidate_hashes(
                formula=formula,
                properties=properties,
                energy_range=energy_range,
                group=group,
                numeric_tolerance=numeric_tolerance,
            )

        results = []
        for hash_val in candidate_hashes:
            structure = self.get(hash_val)
            if structure:
                results.append((hash_val, structure))

        return results

    def get_by_geometry_hash(self, geometry_hash: str) -> List[USIFStructure]:
        """Return all records that share a geometry hash."""
        with self._index_lock:
            record_hashes = list(self._geometry_index.get(geometry_hash, []))

        structures = []
        for record_hash in record_hashes:
            structure = self.get(record_hash)
            if structure is not None:
                structures.append(structure)
        return structures

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
        """Write a checksummed, append-only index generation and commit it."""
        if self.mode == "r" or not self._file:
            return

        with self._file_lock:
            payload = self._serialize_indexes()
            generation = max(self._index_generation + 1, int(time.time_ns()))
            checksum = zlib.crc32(payload) & 0xFFFFFFFF
            manifest = struct.pack(
                self.INDEX_HEADER_FORMAT,
                self.INDEX_MAGIC,
                generation,
                len(payload),
                checksum,
                b"\x00" * 4,
            )
            index_block = manifest + payload + self.INDEX_COMMIT

            try:
                self._file.seek(0, 2)
                index_offset = self._file.tell()
                self._file.write(index_block)
                self._file.flush()
                os.fsync(self._file.fileno())

                # Update header after the generation is durably committed.
                self._file.seek(8)
                self._file.write(struct.pack(BinaryFormat.UINT32, len(self._hash_index)))
                self._file.seek(20)
                self._file.write(struct.pack(BinaryFormat.UINT64, index_offset))
                self._file.seek(54)
                self._file.write(struct.pack(BinaryFormat.UINT64, int(time.time())))
                self._file.flush()
                os.fsync(self._file.fileno())
                self._index_offset = index_offset
                self._index_generation = generation
            except Exception as e:
                raise ContainerIndexError(f"Failed to write enhanced index: {e}") from e

    def _deserialize_indexes(self) -> None:
        """Deserialize a legacy index payload from the current file position."""
        payload = self._file.read()
        self._deserialize_indexes_from_payload(payload, strict=False)

    def _deserialize_indexes_from_payload(self, payload: bytes, *, strict: bool = True) -> None:
        """Deserialize indexes from an in-memory payload."""
        reader = BinaryReader(payload, context="container index payload")

        # Read hash/record index.
        num_hashes = reader.read_u32("hash index count")
        for _ in range(num_hashes):
            struct_hash = reader.read_string_u16("record hash")
            chunk_id = reader.read_u32("chunk id")
            offset = reader.read_u64("chunk offset")
            size = reader.read_u32("record byte size")
            self._hash_index[struct_hash] = (chunk_id, offset, size)

        # Read name index.
        num_names = reader.read_u32("name index count")
        for _ in range(num_names):
            name = reader.read_string_u16("structure name")
            struct_hash = reader.read_string_u16("named record hash")
            self._name_index[name] = struct_hash

        # Read structure attributes.
        num_attrs = reader.read_u32("structure attribute count")
        for _ in range(num_attrs):
            name = reader.read_string_u16("attribute structure name")
            num_attr_pairs = reader.read_u16("structure attribute pair count")
            attrs = {}
            for _ in range(num_attr_pairs):
                attr_name = reader.read_string_u16("attribute name")
                value_len = reader.read_u32("attribute value length")
                value_str = reader.read_bytes(value_len, "attribute value").decode("utf-8")
                try:
                    attrs[attr_name] = (
                        float(value_str) if "." in value_str else int(value_str)
                    )
                except ValueError:
                    attrs[attr_name] = value_str
            self._structure_attributes[name] = attrs

        # Read group hierarchy.
        group_data_len = reader.read_u32("group hierarchy length")
        if group_data_len > 0:
            group_data = reader.read_bytes(group_data_len, "group hierarchy")
            self._deserialize_group_hierarchy(group_data)

        if strict:
            reader.assert_consumed("container index payload")

    def _deserialize_group_hierarchy(self, data: bytes) -> None:
        """Deserialize group hierarchy from bytes with bounds checking."""
        reader = BinaryReader(data, context="container group hierarchy")

        def deserialize_group(parent_path: str = "/") -> USIFGroup:
            name = reader.read_string_u16("group name")
            group = USIFGroup(name)

            if parent_path == "/":
                full_path = f"/{name}/" if name else "/"
            else:
                full_path = f"{parent_path}{name}/"

            if full_path != "/":
                self._group_index[full_path] = group

            num_structs = reader.read_u32("group structure count")
            for _ in range(num_structs):
                struct_name = reader.read_string_u16("group structure name")
                struct_hash = reader.read_string_u16("group structure hash")
                group.structures[struct_name] = struct_hash

            num_attrs = reader.read_u16("group attribute count")
            for _ in range(num_attrs):
                attr_name = reader.read_string_u16("group attribute name")
                value_len = reader.read_u32("group attribute value length")
                value_str = reader.read_bytes(value_len, "group attribute value").decode(
                    "utf-8"
                )
                try:
                    group.attributes[attr_name] = (
                        float(value_str) if "." in value_str else int(value_str)
                    )
                except ValueError:
                    group.attributes[attr_name] = value_str

            num_subgroups = reader.read_u32("group subgroup count")
            for _ in range(num_subgroups):
                subgroup = deserialize_group(full_path)
                group.subgroups[subgroup.name] = subgroup

            return group

        self.root_group = deserialize_group("/")
        reader.assert_consumed("container group hierarchy")

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

    def rebuild_index(self, *, persist: bool = False) -> int:
        """Rebuild the primary record index by scanning USIF records in the file.

        This recovery path is intentionally conservative: it restores record hashes
        and secondary indexes for structure bytes that can be decoded, but names,
        groups, and attributes cannot be reconstructed if the persisted index was
        lost.  When ``persist`` is true and the container is writable, a new
        checksummed index generation is written after rebuilding.

        Returns:
            Number of recovered records.
        """
        if not self._file:
            raise StorageError("Cannot rebuild index on a closed container")

        with self._index_lock, self._file_lock:
            self._file.seek(0)
            file_data = self._file.read()
            scan_limit = self._index_offset if self._index_offset > self.HEADER_SIZE else len(file_data)

            recovered = []
            pos = self.HEADER_SIZE
            while pos + USIF.HEADER_SIZE <= scan_limit:
                if file_data[pos : pos + 7] != b"USIF\x00\x00\x00":
                    pos += 1
                    continue

                try:
                    compressed_size = struct.unpack(
                        BinaryFormat.UINT32, file_data[pos + 12 : pos + 16]
                    )[0]
                    record_size = USIF.HEADER_SIZE + compressed_size
                    if record_size <= USIF.HEADER_SIZE or pos + record_size > scan_limit:
                        pos += 1
                        continue
                    record_data = file_data[pos : pos + record_size]
                    structure, _ = self.encoder.decode(record_data)
                    record_hash = self.encoder.get_record_hash(structure)
                    chunk_id = pos // self.CHUNK_SIZE
                    chunk_offset = pos % self.CHUNK_SIZE
                    recovered.append((record_hash, (chunk_id, chunk_offset, record_size), structure))
                    pos += record_size
                except Exception:
                    pos += 1

            self._clear_loaded_indexes()
            for record_hash, location, structure in recovered:
                self._hash_index[record_hash] = location
                self._indexes.update_secondary(structure, record_hash)

            if persist:
                if self.mode == "r":
                    raise ValueError("Cannot persist rebuilt index in read-only mode")
                self._write_enhanced_index()

            return len(recovered)

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
        write_error = None
        # Write indexes before closing if in write mode.  P1 makes index
        # persistence failures visible instead of only logging a warning.
        if self.mode in ("w", "a") and self._file:
            try:
                self._write_enhanced_index()
            except Exception as e:
                write_error = e
                logger.error(f"Failed to write index on close: {e}")

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

        if write_error is not None:
            raise ContainerIndexError(f"Failed to write index on close: {write_error}") from write_error

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
