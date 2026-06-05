"""Composed record storage for USIF containers."""

from __future__ import annotations

import logging
import mmap
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional, Union

from usif.constants import BinaryFormat
from usif.exceptions import StorageError
from usif.storage.file_store import ChunkedFileStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContainerHeader:
    """Parsed fixed-size USIF container header."""

    version: int
    structure_count: int
    data_offset: int
    index_offset: int
    group_offset: int
    attribute_offset: int
    compression_type: int
    use_chunking: bool
    created_at: int
    updated_at: int


class RecordStore:
    """Owns container file handles, memory mapping, and chunked record I/O."""

    HEADER_SIZE = 64

    def __init__(
        self,
        filename: Union[str, Path],
        *,
        mode: str,
        use_mmap: bool,
        chunk_size: int,
        magic: bytes,
    ) -> None:
        self.filename = Path(filename).resolve()
        self.mode = mode
        self.use_mmap = use_mmap
        self.chunk_size = chunk_size
        self.magic = magic
        self.file_obj: Optional[BinaryIO] = None
        self.mmap_obj: Optional[mmap.mmap] = None

    def open(self) -> None:
        """Open the underlying file and mmap when requested and possible."""
        if self.mode == "r":
            if not self.filename.exists():
                raise FileNotFoundError(f"File not found: {self.filename}")
            self.file_obj = open(self.filename, "rb")
            self._open_mmap(mmap.ACCESS_READ)
            return

        if self.mode == "a" and self.filename.exists():
            self.file_obj = open(self.filename, "r+b")
            self._open_mmap(None)
            return

        self.file_obj = open(self.filename, "w+b")
        self.use_mmap = False

    def _open_mmap(self, access) -> None:
        if not self.use_mmap or self.file_obj is None:
            return
        try:
            if access is None:
                self.mmap_obj = mmap.mmap(self.file_obj.fileno(), 0)
            else:
                self.mmap_obj = mmap.mmap(self.file_obj.fileno(), 0, access=access)
        except Exception as exc:  # pragma: no cover - platform/filesystem dependent
            logger.warning("Failed to create mmap: %s", exc)
            self.use_mmap = False
            self.mmap_obj = None

    def write_header(self, *, compression_value: int) -> None:
        """Write a fresh container header."""
        if self.file_obj is None:
            raise StorageError("RecordStore is not open")
        timestamp = int(time.time())
        header = bytearray(self.HEADER_SIZE)
        header[0:7] = self.magic
        header[7:8] = struct.pack(BinaryFormat.UINT8, 1)
        header[8:12] = struct.pack(BinaryFormat.UINT32, 0)
        header[12:20] = struct.pack(BinaryFormat.UINT64, self.HEADER_SIZE)
        header[20:28] = struct.pack(BinaryFormat.UINT64, 0)
        header[28:36] = struct.pack(BinaryFormat.UINT64, 0)
        header[36:44] = struct.pack(BinaryFormat.UINT64, 0)
        header[44:45] = struct.pack(BinaryFormat.UINT8, compression_value)
        header[45:46] = struct.pack(BinaryFormat.UINT8, 1)
        header[46:54] = struct.pack(BinaryFormat.UINT64, timestamp)
        header[54:62] = struct.pack(BinaryFormat.UINT64, timestamp)
        self.file_obj.seek(0)
        self.file_obj.write(header)
        self.file_obj.flush()

    def chunked(self) -> ChunkedFileStore:
        if self.file_obj is None:
            raise StorageError("RecordStore is not open")
        return ChunkedFileStore(self.file_obj, self.mmap_obj, self.chunk_size)

    def allocate(self, size: int):
        return self.chunked().allocate(size)

    def write_record(self, chunk_id: int, offset: int, data: bytes) -> None:
        self.chunked().write(chunk_id, offset, data)

    def read_record(self, chunk_id: int, offset: int, size: int) -> bytes:
        return self.chunked().read(chunk_id, offset, size)

    def close(self) -> None:
        mmap_obj = self.mmap_obj
        self.mmap_obj = None
        if mmap_obj is not None:
            mmap_obj.close()
        file_obj = self.file_obj
        self.file_obj = None
        if file_obj is not None:
            file_obj.close()
