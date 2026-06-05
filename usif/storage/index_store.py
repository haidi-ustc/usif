"""Index block I/O for USIF containers."""

from __future__ import annotations

import os
import struct
import time
import zlib
from dataclasses import dataclass
from typing import Optional

from usif.constants import BinaryFormat
from usif.exceptions import ContainerIndexError, CorruptedDataError, StorageError
from usif.format.binary import BinaryReader
from usif.storage.record_store import ContainerHeader, RecordStore


@dataclass(frozen=True)
class IndexBlock:
    """A validated container index generation."""

    offset: int
    generation: int
    payload: bytes


class ContainerIndexStore:
    """Read and write append-only container index generations."""

    SCAN_CHUNK_SIZE = 1024 * 1024

    def __init__(
        self,
        record_store: RecordStore,
        *,
        container_magic: bytes,
        index_magic: bytes,
        index_commit: bytes,
        index_header_format: str,
        header_size: int,
        container_version: int,
    ) -> None:
        self.record_store = record_store
        self.container_magic = container_magic
        self.index_magic = index_magic
        self.index_commit = index_commit
        self.index_header_format = index_header_format
        self.header_size = header_size
        self.container_version = container_version

    @property
    def file_obj(self):
        if self.record_store.file_obj is None:
            raise StorageError("RecordStore is not open")
        return self.record_store.file_obj

    def file_size(self) -> int:
        file_obj = self.file_obj
        current = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(current)
        return size

    def read_container_header(self, filename) -> ContainerHeader:
        file_obj = self.file_obj
        file_obj.seek(0)
        header = file_obj.read(self.header_size)
        if len(header) < self.header_size:
            raise CorruptedDataError(
                f"Container is too short: {len(header)} < {self.header_size}"
            )
        reader = BinaryReader(header, context="USIF container header")
        magic = reader.read_bytes(7, "container magic")
        if magic != self.container_magic:
            if magic == b"USIF\x00\x00\x00":
                raise StorageError(
                    f"File {filename} is a USIF structure file, not a container. "
                    "Use usif.services.load_structure() to open it."
                )
            raise CorruptedDataError("Invalid USIF container")
        version = reader.read_u8("container version")
        if version != self.container_version:
            raise ContainerIndexError(
                f"Unsupported USIF container version {version}; expected {self.container_version}"
            )
        return ContainerHeader(
            version=version,
            structure_count=reader.read_u32("structure count"),
            data_offset=reader.read_u64("data offset"),
            index_offset=reader.read_u64("index offset"),
            group_offset=reader.read_u64("group offset"),
            attribute_offset=reader.read_u64("attribute offset"),
            compression_type=reader.read_u8("compression type"),
            use_chunking=bool(reader.read_u8("use chunking")),
            created_at=reader.read_u64("created timestamp"),
            updated_at=reader.read_u64("updated timestamp"),
        )

    def read_index_block_at(self, offset: int) -> IndexBlock:
        file_size = self.file_size()
        if offset < self.header_size or offset >= file_size:
            raise ContainerIndexError(
                f"Index offset {offset} is outside container size {file_size}"
            )
        file_obj = self.file_obj
        current = file_obj.tell()
        try:
            header_size = struct.calcsize(self.index_header_format)
            file_obj.seek(offset)
            header = file_obj.read(header_size)
            if len(header) != header_size:
                raise ContainerIndexError("Truncated index manifest header")
            magic, generation, payload_size, checksum, _reserved = struct.unpack(
                self.index_header_format, header
            )
            if magic != self.index_magic:
                raise ContainerIndexError("Invalid index magic")
            payload = file_obj.read(payload_size)
            if len(payload) != payload_size:
                raise ContainerIndexError("Truncated index payload")
            commit = file_obj.read(len(self.index_commit))
            if commit != self.index_commit:
                raise ContainerIndexError("Missing index commit marker")
            actual_checksum = zlib.crc32(payload) & 0xFFFFFFFF
            if actual_checksum != checksum:
                raise ContainerIndexError(
                    f"Index checksum mismatch: header {checksum:#x}, actual {actual_checksum:#x}"
                )
            return IndexBlock(offset=offset, generation=generation, payload=payload)
        finally:
            file_obj.seek(current)

    def find_latest_valid_index_offset(self) -> Optional[int]:
        """Scan the file in bounded chunks for the newest valid index block."""
        file_obj = self.file_obj
        best_offset = None
        best_generation = -1
        file_obj.seek(self.header_size)
        absolute = self.header_size
        overlap = b""
        magic_len = len(self.index_magic)

        while True:
            chunk = file_obj.read(self.SCAN_CHUNK_SIZE)
            if not chunk:
                break
            data = overlap + chunk
            base = absolute - len(overlap)
            search_from = 0
            while True:
                found = data.find(self.index_magic, search_from)
                if found < 0:
                    break
                offset = base + found
                try:
                    block = self.read_index_block_at(offset)
                    if block.generation > best_generation:
                        best_generation = block.generation
                        best_offset = offset
                except ContainerIndexError:
                    pass
                search_from = found + 1
            overlap = data[-max(magic_len - 1, 0) :]
            absolute += len(chunk)
        return best_offset

    def write_index_block(self, payload: bytes, generation: int) -> int:
        file_obj = self.file_obj
        checksum = zlib.crc32(payload) & 0xFFFFFFFF
        manifest = struct.pack(
            self.index_header_format,
            self.index_magic,
            generation,
            len(payload),
            checksum,
            b"\x00" * 4,
        )
        index_block = manifest + payload + self.index_commit
        file_obj.seek(0, os.SEEK_END)
        index_offset = file_obj.tell()
        file_obj.write(index_block)
        file_obj.flush()
        os.fsync(file_obj.fileno())
        return index_offset

    def update_header_after_index(self, *, structure_count: int, index_offset: int) -> None:
        file_obj = self.file_obj
        file_obj.seek(8)
        file_obj.write(struct.pack(BinaryFormat.UINT32, structure_count))
        file_obj.seek(20)
        file_obj.write(struct.pack(BinaryFormat.UINT64, index_offset))
        file_obj.seek(54)
        file_obj.write(struct.pack(BinaryFormat.UINT64, int(time.time())))
        file_obj.flush()
        os.fsync(file_obj.fileno())
