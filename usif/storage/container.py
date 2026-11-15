"""USIF container storage API.

``StructureContainer`` stores multiple USIF records in one ``.usifc`` file with
record-hash deduplication, name/group indexes, typed JSON metadata, persisted
formula/property/geometry indexes, validation, recovery, and query helpers.

Example:
    >>> from usif.storage import StructureContainer
    >>> with StructureContainer("structures.usifc", mode="w") as container:
    ...     container.add(structure1, name="structure1")
    ...     container.add(structure2, name="structure2")
    ...     container.add(nacl_structure, name="NaCl", group="/crystals")
    >>> with StructureContainer("structures.usifc", mode="r") as container:
    ...     results = container.query(formula="NaCl", has_property="energy")
    ...     structure = container.get("NaCl")
"""

import logging
import queue
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from usif.constants import CompressionType, QueryConstants
from usif.encoder import USIF
from usif.exceptions import (
    ContainerError,
    ContainerIndexError,
    CorruptedDataError,
    DecodingError,
    StorageError,
    ValidationError,
)
from usif.storage.attributes import AttributeCodecMixin
from usif.storage.cache import StructureCache
from usif.storage.group_ops import GroupOperationsMixin
from usif.storage.groups import USIFGroup
from usif.storage.index_persistence import IndexPersistenceMixin
from usif.storage.indexes import ContainerIndexes
from usif.storage.io_ops import StorageIOMixin
from usif.storage.prefetch import PrefetchMixin
from usif.storage.query import QueryEngine
from usif.storage.record_store import RecordStore
from usif.storage.index_store import ContainerIndexStore
from usif.storage.recovery import RecoveryMixin
from usif.storage.validation import ContainerValidationResult, ContainerValidator
from usif.structures.structure import USIFStructure

logger = logging.getLogger(__name__)


def _display_group_path(path: str) -> str:
    """Normalize internal group-index paths for public introspection output."""
    parts = [part for part in str(path).split("/") if part]
    if not parts:
        return "/"
    return "/" + "/".join(parts) + "/"


class StructureContainer(
    AttributeCodecMixin,
    GroupOperationsMixin,
    StorageIOMixin,
    IndexPersistenceMixin,
    PrefetchMixin,
    RecoveryMixin,
):
    """Thread-safe container for indexed multi-structure storage."""

    CONTAINER_MAGIC = b"USIFC\x00\x00"
    CONTAINER_VERSION = 2
    INDEX_MAGIC = b"USIFIDX2"
    INDEX_COMMIT = b"USIFDONE"
    INDEX_HEADER_FORMAT = "<8sQQI4s"
    HEADER_SIZE = 64
    CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB chunks

    def __init__(
        self,
        filename: Union[str, Path],
        mode: str = "r",
        compression: CompressionType = CompressionType.GZIP,
        use_mmap: bool = True,
        cache_size: int = 1000,
        num_workers: int = 4,
        autocommit_every: Optional[int] = None,
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
            autocommit_every: Commit an index generation after this many new
                records (``None`` commits only on :meth:`flush` and
                :meth:`close`). Records added after the last commit are
                recoverable only through :meth:`rebuild_index`.
        """
        if mode not in ("r", "w", "a"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'r', 'w', or 'a'")
        if autocommit_every is not None and autocommit_every < 1:
            raise ValueError("autocommit_every must be a positive integer or None")
        self.autocommit_every = autocommit_every
        self._adds_since_commit = 0
        #: Bytes found after the last committed index when the file was opened.
        #: Non-zero means a writer stopped without committing; see rebuild_index().
        self.uncommitted_bytes = 0

        self.filename = Path(filename).resolve()
        self.mode = mode
        self.encoder = USIF(compression=compression)
        self.use_mmap = use_mmap
        self.num_workers = max(1, min(num_workers, 32))

        # Thread-safe decoded-structure cache
        self._cache = StructureCache(cache_size)

        # Indexes with thread-safe lock
        self._index_lock = threading.RLock()
        self._file_lock = threading.RLock()
        self._indexes = ContainerIndexes()
        self._record_index = self._indexes.record_index  # record_hash -> (chunk, offset, size)
        self._geometry_index = self._indexes.geometry_index
        self._name_index = self._indexes.name_index
        self._formula_index = self._indexes.formula_index
        self._property_index = self._indexes.property_index
        self._group_index = self._indexes.group_index
        self._structure_attributes = self._indexes.structure_attributes

        # Low-level handles are owned by RecordStore and exposed internally only
        # to storage components that operate on validated byte ranges.
        self._record_store = RecordStore(
            self.filename,
            mode=mode,
            use_mmap=use_mmap,
            chunk_size=self.CHUNK_SIZE,
            magic=self.CONTAINER_MAGIC,
            container_version=self.CONTAINER_VERSION,
        )
        self._index_store = ContainerIndexStore(
            self._record_store,
            container_magic=self.CONTAINER_MAGIC,
            index_magic=self.INDEX_MAGIC,
            index_commit=self.INDEX_COMMIT,
            index_header_format=self.INDEX_HEADER_FORMAT,
            header_size=64,
            container_version=self.CONTAINER_VERSION,
        )
        self._file = None
        self._mmap = None

        # Group hierarchy
        self.root_group = USIFGroup("/")

        # Prefetch queue
        self._prefetch_queue = queue.Queue()
        self._prefetch_thread = None

        # Data offsets
        self._data_offset = self.HEADER_SIZE
        self._index_offset = 0
        self._index_generation = 0

        # Initialize record/index stores.
        self._record_store.open()
        self._file = self._record_store.file_obj
        self._mmap = self._record_store.mmap_obj
        self.use_mmap = self._record_store.use_mmap

        if mode in ("r", "a") and self.filename.exists() and self.filename.stat().st_size > 0:
            self._read_enhanced_index()
            self._detect_uncommitted_data()
        elif mode in ("w", "a"):
            self._write_header()

        # Start prefetch thread
        if self._prefetch_queue and num_workers > 0:
            self._start_prefetch_thread()

    def _write_header(self) -> None:
        """Write container header through the composed record store."""
        self._record_store.write_header(
            compression_value=self.encoder.compression.value,
            container_version=self.CONTAINER_VERSION,
        )


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

        attributes = self._validate_structure_metadata(name, group, attributes)

        try:
            usif_data, struct_hash = self.encoder.encode_with_record_hash(structure)

            # Close the check/write/update TOCTOU window.  The index lock
            # guards the record reservation; the file lock is acquired inside it so
            # a second thread cannot pass the duplicate check before this record is
            # fully indexed. Duplicate records are deduplicated at the byte-store
            # level, but new aliases/groups/attributes are still recorded.
            with self._index_lock:
                if struct_hash in self._record_index:
                    logger.info(f"Record {struct_hash[:16]} already exists")
                    self._record_structure_metadata(struct_hash, name, group, attributes)
                    self._indexes.update_secondary(structure, struct_hash)
                    return struct_hash

                with self._file_lock:
                    chunk_id, chunk_offset = self._allocate_space(len(usif_data))
                    self._write_to_chunk(chunk_id, chunk_offset, usif_data)

                self._record_index[struct_hash] = (chunk_id, chunk_offset, len(usif_data))
                self._record_structure_metadata(struct_hash, name, group, attributes)
                self._indexes.update_secondary(structure, struct_hash)
                self._adds_since_commit += 1
                autocommit_due = (
                    self.autocommit_every is not None
                    and self._adds_since_commit >= self.autocommit_every
                )
            if autocommit_due:
                self.flush()

            logger.debug(f"Added structure {struct_hash[:16]} (name: {name or 'N/A'})")

            return struct_hash

        except (StorageError, ContainerError, ValidationError):
            raise
        except Exception as e:
            logger.error(f"Failed to add structure: {e}")
            raise StorageError(f"Failed to add structure: {e}") from e


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
        # Resolve aliases first and cache by record hash: a name can be rebound
        # to another record, a record hash never changes meaning.
        with self._index_lock:
            struct_hash = self._name_index.get(identifier, identifier)

            if struct_hash not in self._record_index:
                return None

            chunk_id, chunk_offset, size = self._record_index[struct_hash]

        cached = self._cache.get(struct_hash)
        if cached is not None:
            return cached.copy()

        usif_data = self._read_from_chunk(chunk_id, chunk_offset, size)

        try:
            structure, _ = self.encoder.decode(usif_data)

            self._cache.put(struct_hash, structure)

            # Callers get their own copy so mutations never reach the cache.
            return structure.copy()

        except (DecodingError, CorruptedDataError) as e:
            logger.error(f"Error decoding structure {identifier}: {e}")
            raise StorageError(f"Failed to decode stored structure {identifier}: {e}") from e
        except Exception as e:
            logger.error(
                f"Unexpected error decoding structure {identifier}: {e}", exc_info=True
            )
            raise StorageError(f"Failed to decode stored structure {identifier}: {e}") from e


    def query(
        self,
        formula: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        energy_range: Optional[Tuple[float, float]] = None,
        group: Optional[str] = None,
        numeric_tolerance: float = QueryConstants.DEFAULT_NUMERIC_TOLERANCE,
        has_property: Optional[str] = None,
        property_range: Optional[Tuple[str, float, float]] = None,
        custom: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, USIFStructure]]:
        """Query structures with indexed criteria.

        Args:
            formula: Exact reduced formula match.
            properties: Exact or tolerance-based property matches.
            energy_range: Convenience range query for ``energy``.
            group: Group path filter.
            numeric_tolerance: Tolerance for scalar numeric property equality.
            has_property: Require a property/dotted custom property to exist.
            property_range: ``(name, min, max)`` numeric range filter.
            custom: Dotted custom-property matches, merged with ``properties``.
        """
        with self._index_lock:
            query_engine = QueryEngine(self._indexes, self.get_group)
            candidate_hashes = query_engine.candidate_hashes(
                formula=formula,
                properties=properties,
                energy_range=energy_range,
                group=group,
                numeric_tolerance=numeric_tolerance,
                has_property=has_property,
                property_range=property_range,
                custom=custom,
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



    def validate(self, *, level: str = "index") -> ContainerValidationResult:
        """Validate container consistency at an explicit assurance level.

        Args:
            level: ``"index"`` validates persisted indexes and metadata only.
                ``"records"`` also reads each record byte range and checks the
                USIF header/length. ``"full"`` decodes every structure and
                verifies its record hash.

        Returns:
            ContainerValidationResult with errors, warnings, and summary counts.
        """
        with self._index_lock:
            return ContainerValidator(self).validate(level=level)

    def list_names(self) -> List[str]:
        """Return sorted structure aliases stored in the container."""
        with self._index_lock:
            return sorted(self._name_index)

    def list_formulas(self) -> List[str]:
        """Return sorted reduced formulas available through the persisted index."""
        with self._index_lock:
            return sorted(self._formula_index)

    def list_properties(self) -> List[str]:
        """Return sorted indexed property and dotted custom-property names."""
        with self._index_lock:
            return sorted(self._property_index)

    def list_groups(self) -> List[str]:
        """Return sorted group paths, including the root group."""
        with self._index_lock:
            groups = {_display_group_path(path) for path in self._group_index}
            groups.add("/")
            return sorted(groups)

    def stats(self) -> Dict[str, Any]:
        """Return lightweight container statistics without decoding records."""
        with self._index_lock:
            record_count = len(self._record_index)
            group_count = len(self._group_index) + 1  # include root group
            record_bytes = sum(size for _, _, size in self._record_index.values())
            record_index_size = record_count * 44
            secondary_index_size = sum(
                len(hashes) * 16 for hashes in self._formula_index.values()
            ) + sum(
                len(bucket_hashes) * 16
                for prop_dict in self._property_index.values()
                for bucket_hashes in prop_dict.values()
            )
            formulas = sorted(self._formula_index)
            properties = sorted(self._property_index)
            group_paths = sorted(
                {_display_group_path(path) for path in self._group_index} | {"/"}
            )

        if self._file:
            file_size = self._index_store.file_size()
        else:
            file_size = self.filename.stat().st_size if self.filename.exists() else 0
        compression_ratio = (record_bytes / file_size) if file_size else 0.0

        return {
            "records": record_count,
            "groups": group_count,
            "unique_formulas": len(formulas),
            "formulas": formulas,
            "properties": properties,
            "group_paths": group_paths,
            "record_bytes": record_bytes,
            "file_size_bytes": file_size,
            "index_size_bytes": record_index_size + secondary_index_size,
            "compression_ratio": compression_ratio,
            "cache": {"entries": len(self._cache)},
            "storage": {
                "compression": self.encoder.compression.name.lower(),
                "mmap": self.use_mmap,
                "chunk_size_bytes": self.CHUNK_SIZE,
            },
        }

    def flush(self) -> None:
        """Commit the current index as a new checksummed generation.

        Records are written to disk as they are added, but they become visible
        to readers (and survive a crash with names, groups and attributes) only
        once an index generation is committed. Index generations are
        append-only, so flushing never rewrites existing data.
        """
        if self.mode == "r":
            raise ValueError("Cannot flush a read-only container")
        if not self._file:
            raise StorageError("Cannot flush a closed container")
        self._write_enhanced_index()

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
        # Write indexes before closing if in write or append mode. Persistence
        # failures are surfaced to callers after resources are released.
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

        self._record_store.close(commit=write_error is None)
        self._file = None
        self._mmap = None

        if write_error is not None:
            raise ContainerIndexError(f"Failed to write index on close: {write_error}") from write_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.close()
        except Exception:
            if exc_type is not None:
                logger.error(
                    "Failed to close container while another exception was active",
                    exc_info=True,
                )
                return False
            raise
        return False

    def __len__(self):
        with self._index_lock:
            return len(self._record_index)

    def __contains__(self, identifier: str):
        with self._index_lock:
            return identifier in self._record_index or identifier in self._name_index

    def __iter__(self):
        with self._index_lock:
            hashes = list(self._record_index)
        for struct_hash in hashes:
            structure = self.get(struct_hash)
            if structure:
                yield struct_hash, structure


