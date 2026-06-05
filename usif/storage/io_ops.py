"""Record I/O adapter for USIF containers."""

from __future__ import annotations

from typing import Tuple


class StorageIOMixin:
    """Delegate chunked record operations to the composed RecordStore."""

    def _allocate_space(self, size: int) -> Tuple[int, int]:
        return self._record_store.allocate(size)

    def _write_to_chunk(self, chunk_id: int, offset: int, data: bytes) -> None:
        self._record_store.write_record(chunk_id, offset, data)

    def _read_from_chunk(self, chunk_id: int, offset: int, size: int) -> bytes:
        with self._file_lock:
            return self._record_store.read_record(chunk_id, offset, size)
