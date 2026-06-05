"""Container data-section recovery helpers."""

from __future__ import annotations

import struct

from usif.constants import BinaryFormat
from usif.encoder import USIF
from usif.exceptions import StorageError


class RecoveryMixin:
    """Conservative record scanner for rebuilding lost indexes."""

    def rebuild_index(self, *, persist: bool = False) -> int:
        """Rebuild the primary record index by scanning USIF records in the file.

        This recovery path is intentionally conservative: it restores record hashes
        and secondary indexes for structure bytes that can be decoded, but names,
        groups, and attributes cannot be reconstructed if the persisted index was
        lost.  When ``persist`` is true and the container is writable, a new
        checksummed index generation is written after rebuilding.

        Returns:
            Number of recovered records.
        """
        if not self._file:
            raise StorageError("Cannot rebuild index on a closed container")

        with self._index_lock, self._file_lock:
            self._file.seek(0)
            file_data = self._file.read()
            scan_limit = self._index_offset if self._index_offset > self.HEADER_SIZE else len(file_data)

            recovered = []
            pos = self.HEADER_SIZE
            while pos + USIF.HEADER_SIZE <= scan_limit:
                if file_data[pos : pos + 7] != b"USIF\x00\x00\x00":
                    pos += 1
                    continue

                try:
                    compressed_size = struct.unpack(
                        BinaryFormat.UINT32, file_data[pos + 12 : pos + 16]
                    )[0]
                    record_size = USIF.HEADER_SIZE + compressed_size
                    if record_size <= USIF.HEADER_SIZE or pos + record_size > scan_limit:
                        pos += 1
                        continue
                    record_data = file_data[pos : pos + record_size]
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

            if persist:
                if self.mode == "r":
                    raise ValueError("Cannot persist rebuilt index in read-only mode")
                self._write_enhanced_index()

            return len(recovered)
