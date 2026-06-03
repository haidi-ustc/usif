"""Chunked file access helpers for USIF containers."""


class ChunkedFileStore:
    """Small adapter for chunk-offset file reads and writes."""

    def __init__(self, file_obj, mmap_obj=None, chunk_size: int = 64 * 1024 * 1024):
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
