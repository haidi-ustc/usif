"""Container data-section recovery helpers."""

from __future__ import annotations

import os
import struct

from usif.constants import BinaryFormat
from usif.encoder import USIF
from usif.exceptions import StorageError


class RecoveryMixin:
    """Conservative streaming record scanner for rebuilding lost indexes."""

    def rebuild_index(self, *, persist: bool = False) -> int:
        """Rebuild indexes by scanning the record data section.

        The scanner reads bounded record-sized slices instead of materializing
        the whole container file.  It restores record hashes and secondary
        indexes for records that can be decoded.  Names, groups, and attributes
        cannot be reconstructed when the persisted index is lost.

        Returns:
            Number of recovered records.
        """
        if not self._file:
            raise StorageError("Cannot rebuild index on a closed container")

        with self._index_lock, self._file_lock:
            recovered = []
            scan_limit = self._scan_limit_for_recovery()
            pos = self.HEADER_SIZE

            while pos + USIF.HEADER_SIZE <= scan_limit:
                self._file.seek(pos)
                header = self._file.read(USIF.HEADER_SIZE)
                if len(header) < USIF.HEADER_SIZE:
                    break
                if header[:7] != b"USIF\x00\x00\x00":
                    pos += 1
                    continue

                try:
                    compressed_size = struct.unpack(BinaryFormat.UINT32, header[12:16])[0]
                    record_size = USIF.HEADER_SIZE + compressed_size
                    if record_size <= USIF.HEADER_SIZE or pos + record_size > scan_limit:
                        pos += 1
                        continue
                    self._file.seek(pos)
                    record_data = self._file.read(record_size)
                    if len(record_data) != record_size:
                        break
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
                self._record_index[record_hash] = location
                self._indexes.update_secondary(structure, record_hash)
            self._indexes.secondary_indexes_complete = True

            if persist:
                if self.mode == "r":
                    raise ValueError("Cannot persist rebuilt index in read-only mode")
                self._write_enhanced_index()

            return len(recovered)

    def _scan_limit_for_recovery(self) -> int:
        current = self._file.tell()
        try:
            self._file.seek(0, os.SEEK_END)
            file_size = self._file.tell()
        finally:
            self._file.seek(current)
        if self._index_offset > self.HEADER_SIZE:
            return min(self._index_offset, file_size)
        return file_size
