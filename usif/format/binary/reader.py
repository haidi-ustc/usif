"""Bounds-checked binary reader helpers for USIF payloads."""

import struct
from typing import Any

from usif.constants import BinaryFormat
from usif.exceptions import CorruptedDataError, DecodingError
from usif.format.binary.limits import MAX_STRING_LENGTH


class BinaryReader:
    """Read primitive values from bytes while enforcing bounds.

    All short reads are reported as ``CorruptedDataError`` instead of leaking
    low-level ``struct.error``/``IndexError`` exceptions to callers.
    """

    def __init__(self, data: bytes, *, context: str = "USIF payload"):
        self.data = data
        self.offset = 0
        self.context = context

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def tell(self) -> int:
        return self.offset

    def seek(self, offset: int) -> None:
        if offset < 0 or offset > len(self.data):
            raise CorruptedDataError(
                f"Invalid seek in {self.context}: {offset} outside 0..{len(self.data)}"
            )
        self.offset = offset

    def require(self, size: int, label: str = "field") -> None:
        if size < 0:
            raise CorruptedDataError(f"Invalid negative read size for {label}: {size}")
        if self.remaining < size:
            raise CorruptedDataError(
                f"Truncated {self.context}: need {size} bytes for {label} at offset "
                f"{self.offset}, only {self.remaining} remain"
            )

    def read_bytes(self, size: int, label: str = "bytes") -> bytes:
        self.require(size, label)
        start = self.offset
        self.offset += size
        return self.data[start : start + size]

    def read_struct(self, fmt: str, label: str = "field") -> Any:
        size = struct.calcsize(fmt)
        raw = self.read_bytes(size, label)
        try:
            values = struct.unpack(fmt, raw)
        except struct.error as e:
            raise DecodingError(f"Failed to unpack {label} at offset {self.offset - size}: {e}") from e
        return values[0] if len(values) == 1 else values

    def read_u8(self, label: str = "uint8") -> int:
        return int(self.read_struct(BinaryFormat.UINT8, label))

    def read_u16(self, label: str = "uint16") -> int:
        return int(self.read_struct(BinaryFormat.UINT16, label))

    def read_u32(self, label: str = "uint32") -> int:
        return int(self.read_struct(BinaryFormat.UINT32, label))

    def read_u64(self, label: str = "uint64") -> int:
        return int(self.read_struct(BinaryFormat.UINT64, label))

    def read_f32(self, label: str = "float32") -> float:
        return float(self.read_struct(BinaryFormat.FLOAT32, label))

    def read_f32_tuple3(self, label: str = "float32[3]"):
        return tuple(self.read_struct(BinaryFormat.array(BinaryFormat.FLOAT32, 3), label))

    def read_string_u8(self, label: str = "string") -> str:
        length = self.read_u8(f"{label} length")
        return self.read_string(length, label)

    def read_string_u16(self, label: str = "string") -> str:
        length = self.read_u16(f"{label} length")
        return self.read_string(length, label)

    def read_string(self, length: int, label: str = "string") -> str:
        if length > MAX_STRING_LENGTH:
            raise CorruptedDataError(
                f"{label} length {length} exceeds maximum {MAX_STRING_LENGTH}"
            )
        raw = self.read_bytes(length, label)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise DecodingError(f"Invalid UTF-8 for {label} at offset {self.offset - length}: {e}") from e

    def assert_consumed(self, label: str = "payload") -> None:
        if self.remaining != 0:
            raise CorruptedDataError(
                f"Trailing data after {label}: {self.remaining} unconsumed bytes at offset {self.offset}"
            )
