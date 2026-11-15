"""Index manifest serialization and recovery for USIF containers."""

from __future__ import annotations

import json
import logging
import struct
import time
from collections import defaultdict
from typing import Any, DefaultDict, Optional

from usif.constants import BinaryFormat
from usif.exceptions import (
    ContainerIndexError,
    CorruptedDataError,
    StorageError,
)
from usif.format.binary import BinaryReader
from usif.storage.groups import USIFGroup
from usif.storage.indexes import HashBucket, make_index_key

logger = logging.getLogger(__name__)

SECONDARY_INDEX_MAGIC = b"SIDX0002"


class IndexPersistenceMixin:
    """Append-only, checksummed container index persistence."""

    def _read_enhanced_index(self) -> None:
        """Read the container header and load the newest valid index generation.

        The normal path reads only the fixed header plus the referenced index
        block, instead of materializing the entire container file in memory.
        A bounded streaming scan is used only when the header points to a bad
        generation.
        """
        try:
            header = self._index_store.read_container_header(self.filename)
            if header.version != self.CONTAINER_VERSION:
                raise ContainerIndexError(
                    f"Unsupported USIF container version {header.version}; "
                    f"expected {self.CONTAINER_VERSION}"
                )
            self._data_offset = header.data_offset
            self._index_offset = header.index_offset

            if header.index_offset <= 0:
                if header.structure_count and self.mode != "a":
                    raise ContainerIndexError("Container header has records but no committed index")
                return

            try:
                self._deserialize_index_at(header.index_offset)
            except ContainerIndexError as e:
                logger.warning("Header index generation is invalid: %s", e)
                recovered = self._find_latest_valid_index_offset()
                if recovered is None:
                    raise
                logger.info("Recovered container index generation at offset %s", recovered)
                self._deserialize_index_at(recovered)
                self._index_offset = recovered

        except (StorageError, CorruptedDataError, ContainerIndexError):
            raise
        except Exception as e:
            logger.error(f"Failed to read index: {e}")
            raise StorageError(f"Failed to read container index: {e}") from e

    def _detect_uncommitted_data(self) -> None:
        """Warn when bytes exist after the last committed index generation.

        That happens when a writer crashed or never called ``close()``/``flush()``.
        The records are still on disk and :meth:`rebuild_index` can recover them.
        """
        file_size = self._index_store.file_size()
        if self._index_offset > 0:
            block = self._index_store.read_index_block_at(self._index_offset)
            committed_end = self._index_offset + self._index_store.block_size(block)
        else:
            committed_end = self.HEADER_SIZE
        self.uncommitted_bytes = max(0, file_size - committed_end)
        if self.uncommitted_bytes:
            logger.warning(
                "%s has %d bytes after its last committed index; records written "
                "after the last flush()/close() are not indexed. Open with mode='a' "
                "and call rebuild_index(persist=True) to recover them.",
                self.filename,
                self.uncommitted_bytes,
            )

    def _clear_loaded_indexes(self) -> None:
        """Clear index state before loading a persisted generation."""
        self._record_index.clear()
        self._geometry_index.clear()
        self._name_index.clear()
        self._formula_index.clear()
        self._property_index.clear()
        self._group_index.clear()
        self._structure_attributes.clear()
        self.root_group = USIFGroup("/")
        self._cache.clear()

    def _deserialize_index_at(self, offset: int) -> None:
        """Load a checksummed index manifest at ``offset``."""
        block = self._index_store.read_index_block_at(offset)
        self._clear_loaded_indexes()
        try:
            self._deserialize_indexes_from_payload(block.payload)
        except Exception as e:
            raise ContainerIndexError(f"Invalid index payload: {e}") from e
        self._index_generation = block.generation

    def _find_latest_valid_index_offset(self) -> Optional[int]:
        """Return the newest valid append-only index generation offset."""
        return self._index_store.find_latest_valid_index_offset()

    def _write_enhanced_index(self) -> None:
        """Write a checksummed, append-only index generation and commit it."""
        if self.mode == "r" or not self._file:
            return

        # The index lock keeps add()/metadata mutators from changing the
        # dictionaries while they are serialized (lock order: index, then file).
        with self._index_lock, self._file_lock:
            payload = self._serialize_indexes()
            generation = max(self._index_generation + 1, int(time.time_ns()))
            try:
                index_offset = self._index_store.write_index_block(payload, generation)
                self._index_store.update_header_after_index(
                    structure_count=len(self._record_index), index_offset=index_offset
                )
                self._index_offset = index_offset
                self._index_generation = generation
                self._adds_since_commit = 0
            except Exception as e:
                raise ContainerIndexError(f"Failed to write enhanced index: {e}") from e

    def _deserialize_indexes_from_payload(self, payload: bytes) -> None:
        """Deserialize indexes from an in-memory manifest payload."""
        reader = BinaryReader(payload, context="container index payload")

        # Read hash/record index.
        num_hashes = reader.read_u32("record index count")
        for _ in range(num_hashes):
            struct_hash = reader.read_string_u16("record hash")
            chunk_id = reader.read_u32("chunk id")
            offset = reader.read_u64("chunk offset")
            size = reader.read_u32("record byte size")
            self._record_index[struct_hash] = (chunk_id, offset, size)

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
                value_bytes = reader.read_bytes(value_len, "attribute value")
                attrs[attr_name] = self._decode_attribute_value(value_bytes)
            self._structure_attributes[name] = attrs

        # Read group hierarchy.
        group_data_len = reader.read_u32("group hierarchy length")
        if group_data_len > 0:
            group_data = reader.read_bytes(group_data_len, "group hierarchy")
            self._deserialize_group_hierarchy(group_data)

        # Current index payloads always contain persisted secondary indexes.
        if reader.remaining <= 0:
            raise ContainerIndexError("Missing secondary index section")
        magic = reader.read_bytes(len(SECONDARY_INDEX_MAGIC), "secondary index magic")
        if magic != SECONDARY_INDEX_MAGIC:
            raise ContainerIndexError("Invalid secondary index magic")
        secondary_len = reader.read_u32("secondary index payload length")
        secondary_payload = reader.read_bytes(secondary_len, "secondary index payload")
        self._deserialize_secondary_indexes(secondary_payload)

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
                value_bytes = reader.read_bytes(value_len, "group attribute value")
                group.attributes[attr_name] = self._decode_attribute_value(value_bytes)

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

        # Serialize record index
        data.extend(struct.pack(BinaryFormat.UINT32, len(self._record_index)))
        for struct_hash, (chunk_id, offset, size) in self._record_index.items():
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
                value_bytes = self._encode_attribute_value(attr_value)
                data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
                data.extend(value_bytes)

        # Serialize group hierarchy
        group_data = self._serialize_group_hierarchy()
        data.extend(struct.pack(BinaryFormat.UINT32, len(group_data)))
        data.extend(group_data)

        # Serialize persisted secondary indexes so read-only opens do not decode
        # every record just to answer formula/property/geometry queries.
        secondary_data = self._serialize_secondary_indexes()
        data.extend(SECONDARY_INDEX_MAGIC)
        data.extend(struct.pack(BinaryFormat.UINT32, len(secondary_data)))
        data.extend(secondary_data)

        return bytes(data)


    @staticmethod
    def _encode_secondary_key(value: Any) -> Any:
        if isinstance(value, tuple):
            return {"__tuple__": [IndexPersistenceMixin._encode_secondary_key(item) for item in value]}
        return value

    @staticmethod
    def _decode_secondary_key(value: Any) -> Any:
        if isinstance(value, dict) and set(value) == {"__tuple__"}:
            return tuple(IndexPersistenceMixin._decode_secondary_key(item) for item in value["__tuple__"])
        return make_index_key(value)

    def _serialize_secondary_indexes(self) -> bytes:
        """Serialize formula, geometry, and property indexes as deterministic JSON."""
        payload = {
            "geometry_index": {key: list(values) for key, values in self._geometry_index.items()},
            "formula_index": {key: list(values) for key, values in self._formula_index.items()},
            "property_index": {
                prop_name: [
                    {
                        "value": self._encode_secondary_key(bucket),
                        "hashes": list(record_hashes),
                    }
                    for bucket, record_hashes in buckets.items()
                ]
                for prop_name, buckets in self._property_index.items()
            },
        }
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def _deserialize_secondary_indexes(self, payload: bytes) -> None:
        """Load persisted secondary indexes from a JSON payload."""
        try:
            raw = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContainerIndexError(f"Invalid secondary index payload: {exc}") from exc

        geometry_index: DefaultDict[str, HashBucket] = defaultdict(dict)
        for key, values in raw.get("geometry_index", {}).items():
            geometry_index[str(key)] = dict.fromkeys(values)

        formula_index: DefaultDict[str, HashBucket] = defaultdict(dict)
        for key, values in raw.get("formula_index", {}).items():
            formula_index[str(key)] = dict.fromkeys(values)

        property_index: DefaultDict[str, DefaultDict[Any, HashBucket]] = defaultdict(
            lambda: defaultdict(dict)
        )
        for prop_name, entries in raw.get("property_index", {}).items():
            for entry in entries:
                key = self._decode_secondary_key(entry["value"])
                property_index[str(prop_name)][key] = dict.fromkeys(entry.get("hashes", []))

        with self._index_lock:
            self._geometry_index.clear()
            self._geometry_index.update(geometry_index)
            self._formula_index.clear()
            self._formula_index.update(formula_index)
            self._property_index.clear()
            self._property_index.update(property_index)
            self._indexes.secondary_indexes_complete = True

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
                value_bytes = self._encode_attribute_value(attr_value)
                data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
                data.extend(value_bytes)

            # Subgroups
            data.extend(struct.pack(BinaryFormat.UINT32, len(group.subgroups)))
            for subgroup in group.subgroups.values():
                data.extend(serialize_group(subgroup))

            return bytes(data)

        return serialize_group(self.root_group)
