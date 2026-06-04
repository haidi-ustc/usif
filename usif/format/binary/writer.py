"""Safe binary writer helpers for USIF payloads."""

import struct
from typing import Union

from usif.constants import BinaryFormat
from usif.exceptions import EncodingError
from usif.format.binary.limits import MAX_STRING_LENGTH


class BinaryWriter:
    """Small byte buffer wrapper that checks integer and string bounds."""

    def __init__(self):
        self._data = bytearray()

    def extend(self, data: Union[bytes, bytearray]) -> None:
        self._data.extend(data)

    def write_struct(self, fmt: str, *values, label: str = "field") -> None:
        try:
            self._data.extend(struct.pack(fmt, *values))
        except struct.error as e:
            raise EncodingError(f"Failed to encode {label}: {e}") from e

    def write_u8(self, value: int, label: str = "uint8") -> None:
        if not 0 <= int(value) <= 0xFF:
            raise EncodingError(f"{label} value {value} is outside uint8 range")
        self.write_struct(BinaryFormat.UINT8, int(value), label=label)

    def write_u16(self, value: int, label: str = "uint16") -> None:
        if not 0 <= int(value) <= 0xFFFF:
            raise EncodingError(f"{label} value {value} is outside uint16 range")
        self.write_struct(BinaryFormat.UINT16, int(value), label=label)

    def write_u32(self, value: int, label: str = "uint32") -> None:
        if not 0 <= int(value) <= 0xFFFFFFFF:
            raise EncodingError(f"{label} value {value} is outside uint32 range")
        self.write_struct(BinaryFormat.UINT32, int(value), label=label)

    def write_u64(self, value: int, label: str = "uint64") -> None:
        if not 0 <= int(value) <= 0xFFFFFFFFFFFFFFFF:
            raise EncodingError(f"{label} value {value} is outside uint64 range")
        self.write_struct(BinaryFormat.UINT64, int(value), label=label)

    def write_f32(self, value: float, label: str = "float32") -> None:
        self.write_struct(BinaryFormat.FLOAT32, float(value), label=label)

    def write_f32_tuple3(self, values, label: str = "float32[3]") -> None:
        if len(values) != 3:
            raise EncodingError(f"{label} must contain exactly 3 values")
        self.write_struct(
            BinaryFormat.array(BinaryFormat.FLOAT32, 3),
            float(values[0]),
            float(values[1]),
            float(values[2]),
            label=label,
        )

    def write_string_u8(self, value: str, label: str = "string") -> None:
        raw = value.encode("utf-8")
        if len(raw) > 0xFF:
            raise EncodingError(f"{label} is too long for uint8 length: {len(raw)}")
        self.write_u8(len(raw), f"{label} length")
        self.extend(raw)

    def write_string_u16(self, value: str, label: str = "string") -> None:
        raw = value.encode("utf-8")
        if len(raw) > MAX_STRING_LENGTH:
            raise EncodingError(f"{label} length {len(raw)} exceeds maximum {MAX_STRING_LENGTH}")
        if len(raw) > 0xFFFF:
            raise EncodingError(f"{label} is too long for uint16 length: {len(raw)}")
        self.write_u16(len(raw), f"{label} length")
        self.extend(raw)

    def __bytes__(self) -> bytes:
        return bytes(self._data)

    def __len__(self) -> int:
        return len(self._data)
