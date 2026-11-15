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
            seen = set()
            for pos, size, structure in self._iter_records():
                record_hash = self.encoder.get_record_hash(structure)
                if record_hash in seen:
                    continue  # duplicate payload; the first copy is indexed
                seen.add(record_hash)
                location = (pos // self.CHUNK_SIZE, pos % self.CHUNK_SIZE, size)
                recovered.append((record_hash, location, structure))

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

    SCAN_BLOCK_SIZE = 8 * 1024 * 1024
    RECORD_MAGIC = b"USIF\x00\x00\x00"

    def _iter_records(self):
        """Yield ``(offset, size, structure)`` for every decodable record in the file.

        The whole file is scanned, including bytes after the last committed
        index generation: those are exactly the records a crashed writer left
        behind. The search is buffered (``bytes.find`` over large blocks), so
        chunk padding and index blocks are skipped without per-byte syscalls.
        After a record decodes, the scan resumes at its end, so record-magic
        bytes inside a payload are never mistaken for a record.
        """
        file_size = self._file_size_for_recovery()
        header_size = USIF.HEADER_SIZE
        pos = self.HEADER_SIZE
        while pos + header_size <= file_size:
            found = self._find_magic(pos, file_size)
            if found is None:
                return
            self._file.seek(found)
            header = self._file.read(header_size)
            if len(header) < header_size:
                return
            compressed_size = struct.unpack(BinaryFormat.UINT32, header[12:16])[0]
            record_size = header_size + compressed_size
            if compressed_size == 0 or found + record_size > file_size:
                pos = found + 1
                continue
            self._file.seek(found)
            record_data = self._file.read(record_size)
            try:
                structure, _ = self.encoder.decode(record_data)
            except Exception:
                pos = found + 1
                continue
            yield found, record_size, structure
            pos = found + record_size

    def _find_magic(self, start: int, file_size: int):
        """Return the absolute offset of the next record magic at/after ``start``."""
        magic = self.RECORD_MAGIC
        offset = start
        while offset < file_size:
            self._file.seek(offset)
            block = self._file.read(self.SCAN_BLOCK_SIZE + len(magic) - 1)
            if not block:
                return None
            idx = block.find(magic)
            if idx >= 0:
                return offset + idx
            offset += self.SCAN_BLOCK_SIZE
        return None

    def _file_size_for_recovery(self) -> int:
        current = self._file.tell()
        try:
            self._file.seek(0, os.SEEK_END)
            return self._file.tell()
        finally:
            self._file.seek(current)
