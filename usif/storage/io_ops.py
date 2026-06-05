"""Chunked storage I/O operations for USIF containers."""

from __future__ import annotations

from typing import Tuple

from usif.storage.file_store import ChunkedFileStore


class StorageIOMixin:
    """Thin adapter from container locks to chunked file storage."""

    def _file_store(self) -> ChunkedFileStore:
        """Create a chunked storage adapter for current file handles."""
        return ChunkedFileStore(self._file, self._mmap, self.CHUNK_SIZE)

    def _allocate_space(self, size: int) -> Tuple[int, int]:
        """Allocate space in chunked storage."""
        return self._file_store().allocate(size)

    def _write_to_chunk(self, chunk_id: int, offset: int, data: bytes) -> None:
        """Write data to specific chunk."""
        self._file_store().write(chunk_id, offset, data)

    def _read_from_chunk(self, chunk_id: int, offset: int, size: int) -> bytes:
        """Read data from specific chunk (thread-safe)."""
        with self._file_lock:
            return self._file_store().read(chunk_id, offset, size)
