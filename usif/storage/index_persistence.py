"""Index manifest serialization and recovery for USIF containers."""

from __future__ import annotations

import logging
import os
import struct
import time
import zlib
from typing import Optional

from usif.constants import BinaryFormat
from usif.exceptions import (
    ContainerIndexError,
    CorruptedDataError,
    StorageError,
)
from usif.format.binary import BinaryReader
from usif.storage.groups import USIFGroup

logger = logging.getLogger(__name__)


class IndexPersistenceMixin:
    """Append-only, checksummed container index persistence."""

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
        self._cache.clear()

    def _deserialize_index_at(self, data: bytes, offset: int) -> None:
        """Load a checksummed index manifest at ``offset``."""
        if offset < self.HEADER_SIZE or offset >= len(data):
            raise ContainerIndexError(
                f"Index offset {offset} is outside container size {len(data)}"
            )

        if data[offset : offset + len(self.INDEX_MAGIC)] != self.INDEX_MAGIC:
            raise ContainerIndexError("Missing index manifest magic")

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
            self._deserialize_indexes_from_payload(payload)
        except Exception as e:
            raise ContainerIndexError(f"Invalid index payload: {e}") from e
        self._index_generation = generation

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
                    self._update_secondary_indexes(structure, stored_hash)

                if (i + 1) % 100 == 0:
                    logger.info(f"Indexed {i + 1}/{total} structures...")

            except Exception as e:
                logger.warning(f"Failed to index structure {stored_hash[:16]}: {e}")

        logger.info(f"Secondary indexing complete: {total} structures indexed")

    def _update_secondary_indexes(
        self, structure: USIFStructure, struct_hash: str
    ) -> None:
        """Update secondary indexes for a structure (thread-safe)."""
        with self._index_lock:
            self._indexes.update_secondary(structure, struct_hash)

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

    def _deserialize_indexes_from_payload(self, payload: bytes) -> None:
        """Deserialize indexes from an in-memory manifest payload."""
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
                value_bytes = reader.read_bytes(value_len, "attribute value")
                attrs[attr_name] = self._decode_attribute_value(value_bytes)
            self._structure_attributes[name] = attrs

        # Read group hierarchy.
        group_data_len = reader.read_u32("group hierarchy length")
        if group_data_len > 0:
            group_data = reader.read_bytes(group_data_len, "group hierarchy")
            self._deserialize_group_hierarchy(group_data)

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
                value_bytes = self._encode_attribute_value(attr_value)
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
                value_bytes = self._encode_attribute_value(attr_value)
                data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
                data.extend(value_bytes)

            # Subgroups
            data.extend(struct.pack(BinaryFormat.UINT32, len(group.subgroups)))
            for subgroup in group.subgroups.values():
                data.extend(serialize_group(subgroup))

            return bytes(data)

        return serialize_group(self.root_group)
