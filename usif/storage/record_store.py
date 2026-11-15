"""Composed record storage for USIF containers."""

from __future__ import annotations

import logging
import mmap
import os
import struct
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional, Union

from usif.constants import BinaryFormat
from usif.exceptions import ContainerError, StorageError
from usif.fileio import fsync_directory

try:  # POSIX advisory locks; other platforms run without inter-process locking.
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _try_lock_exclusive(file_obj: BinaryIO, path: Path) -> None:
    """Take a non-blocking exclusive advisory lock or raise ContainerError."""
    if fcntl is None:
        return
    try:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise ContainerError(
            f"{path} is already open for writing by another container instance"
        ) from exc


class ChunkedRecordAccess:
    """Chunk-offset file reads and writes owned by RecordStore."""

    def __init__(self, file_obj: BinaryIO, mmap_obj: Optional[mmap.mmap], chunk_size: int):
        self.file_obj = file_obj
        self.mmap_obj = mmap_obj
        self.chunk_size = chunk_size

    def allocate(self, size: int):
        if self.mmap_obj:
            current_pos = self.mmap_obj.size()
        else:
            self.file_obj.seek(0, 2)
            current_pos = self.file_obj.tell()

        chunk_id = current_pos // self.chunk_size
        chunk_offset = current_pos % self.chunk_size

        if chunk_offset + size > self.chunk_size:
            chunk_id += 1
            chunk_offset = 0
            if self.mmap_obj:
                self.mmap_obj.resize(chunk_id * self.chunk_size)
            else:
                padding_size = self.chunk_size - (current_pos % self.chunk_size)
                if padding_size > 0:
                    self.file_obj.write(b"\x00" * padding_size)
                    self.file_obj.flush()

        return chunk_id, chunk_offset

    def write(self, chunk_id: int, offset: int, data: bytes) -> None:
        actual_offset = chunk_id * self.chunk_size + offset

        if self.mmap_obj:
            required_size = actual_offset + len(data)
            if required_size > self.mmap_obj.size():
                self.mmap_obj.resize(required_size)
            self.mmap_obj[actual_offset : actual_offset + len(data)] = data
            self.mmap_obj.flush()
            return

        self.file_obj.seek(0, 2)
        file_size = self.file_obj.tell()
        required_size = actual_offset + len(data)
        if required_size > file_size and actual_offset > file_size:
            self.file_obj.write(b"\x00" * (actual_offset - file_size))

        self.file_obj.seek(actual_offset)
        self.file_obj.write(data)
        self.file_obj.flush()

    def read(self, chunk_id: int, offset: int, size: int) -> bytes:
        actual_offset = chunk_id * self.chunk_size + offset

        if self.mmap_obj:
            return bytes(self.mmap_obj[actual_offset : actual_offset + size])

        current_pos = self.file_obj.tell()
        self.file_obj.seek(actual_offset)
        data = self.file_obj.read(size)
        self.file_obj.seek(current_pos)
        return data



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
        container_version: int,
    ) -> None:
        self.filename = Path(filename).resolve()
        self.mode = mode
        self.use_mmap = use_mmap
        self.chunk_size = chunk_size
        self.magic = magic
        self.container_version = container_version
        self.file_obj: Optional[BinaryIO] = None
        self.mmap_obj: Optional[mmap.mmap] = None
        # Mode "w" writes a temporary sibling file and replaces the target only
        # on a successful close, so an existing container is never truncated.
        self._temp_path: Optional[Path] = None
        # Handle on the target that carries the writer lock in mode "w".
        self._lock_obj: Optional[BinaryIO] = None

    def open(self) -> None:
        """Open the underlying file and mmap when requested and possible.

        Writers (modes ``"a"`` and ``"w"``) hold an exclusive advisory lock on
        the container so two writers cannot interleave records. Readers take no
        lock: appends never move committed bytes, and ``"w"`` replaces the file
        atomically, so an open reader keeps a consistent snapshot.
        """
        if self.mode == "r":
            if not self.filename.exists():
                raise FileNotFoundError(f"File not found: {self.filename}")
            self.file_obj = open(self.filename, "rb")
            self._open_mmap(mmap.ACCESS_READ)
            return

        if self.mode == "a" and self.filename.exists():
            self.file_obj = open(self.filename, "r+b")
            try:
                _try_lock_exclusive(self.file_obj, self.filename)
            except BaseException:
                self.file_obj.close()
                self.file_obj = None
                raise
            self._open_mmap(None)
            return

        # Lock the target itself (created empty if missing) so "w" and "a"
        # writers exclude each other, then write into a temporary sibling.
        self._lock_obj = open(self.filename, "ab")
        try:
            _try_lock_exclusive(self._lock_obj, self.filename)
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{self.filename.name}.", suffix=".tmp", dir=self.filename.parent
            )
        except BaseException:
            self._lock_obj.close()
            self._lock_obj = None
            raise
        self._temp_path = Path(tmp_name)
        self.file_obj = os.fdopen(fd, "w+b")
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

    def write_header(self, *, compression_value: int, container_version: int) -> None:
        """Write a fresh container header."""
        if self.file_obj is None:
            raise StorageError("RecordStore is not open")
        timestamp = int(time.time())
        header = bytearray(self.HEADER_SIZE)
        header[0:7] = self.magic
        header[7:8] = struct.pack(BinaryFormat.UINT8, container_version)
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

    def chunked(self) -> ChunkedRecordAccess:
        if self.file_obj is None:
            raise StorageError("RecordStore is not open")
        return ChunkedRecordAccess(self.file_obj, self.mmap_obj, self.chunk_size)

    def allocate(self, size: int):
        return self.chunked().allocate(size)

    def write_record(self, chunk_id: int, offset: int, data: bytes) -> None:
        self.chunked().write(chunk_id, offset, data)

    def read_record(self, chunk_id: int, offset: int, size: int) -> bytes:
        return self.chunked().read(chunk_id, offset, size)

    def close(self, *, commit: bool = True) -> None:
        """Release handles; in mode ``"w"`` publish the new file if ``commit``.

        When ``commit`` is false (the final index could not be written) the
        original container is left untouched and the new data is kept in the
        temporary file, whose path is logged so it can be recovered.
        """
        mmap_obj = self.mmap_obj
        self.mmap_obj = None
        if mmap_obj is not None:
            mmap_obj.close()
        file_obj = self.file_obj
        self.file_obj = None
        try:
            if file_obj is not None:
                if self._temp_path is not None and commit:
                    file_obj.flush()
                    os.fsync(file_obj.fileno())
                file_obj.close()
            if self._temp_path is not None:
                if commit:
                    os.replace(self._temp_path, self.filename)
                    fsync_directory(self.filename.parent)
                else:
                    logger.error(
                        "Container %s was not replaced; uncommitted data kept in %s",
                        self.filename,
                        self._temp_path,
                    )
                self._temp_path = None
        finally:
            lock_obj = self._lock_obj
            self._lock_obj = None
            if lock_obj is not None:
                lock_obj.close()
