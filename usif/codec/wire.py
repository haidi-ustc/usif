"""Little-endian, bounds-checked byte primitives for the USIF codecs."""

from __future__ import annotations

import struct
from typing import Any, Union

import numpy as np

from usif.errors import FormatError, ValidationError

__all__ = ["ByteReader", "ByteWriter"]

Buffer = Union[bytes, bytearray, memoryview]

_U8 = struct.Struct("<B")
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_U64 = struct.Struct("<Q")
_F64 = struct.Struct("<d")

MAX_STRING_BYTES = 65535


class ByteWriter:
    """Append-only little-endian writer."""

    __slots__ = ("_buffer",)

    def __init__(self) -> None:
        self._buffer = bytearray()

    def u8(self, value: int) -> None:
        self._buffer += _U8.pack(value)

    def u16(self, value: int) -> None:
        self._buffer += _U16.pack(value)

    def u32(self, value: int) -> None:
        self._buffer += _U32.pack(value)

    def u64(self, value: int) -> None:
        self._buffer += _U64.pack(value)

    def f64(self, value: float) -> None:
        self._buffer += _F64.pack(value)

    def raw(self, data: Buffer) -> None:
        self._buffer += data

    def array(self, array: np.ndarray) -> None:
        """Append the little-endian C-order bytes of ``array`` (in its own dtype).

        Callers cast to the wire dtype first; this only fixes the byte order.
        """
        little = array.astype(array.dtype.newbyteorder("<"), copy=False)
        self._buffer += np.ascontiguousarray(little).tobytes()

    def string(self, text: str) -> None:
        """UTF-8 string with a u16 byte-length prefix."""
        data = text.encode("utf-8")
        if len(data) > MAX_STRING_BYTES:
            raise ValidationError(f"string of {len(data)} bytes exceeds {MAX_STRING_BYTES}")
        self.u16(len(data))
        self._buffer += data

    def __len__(self) -> int:
        return len(self._buffer)

    def getvalue(self) -> bytes:
        return bytes(self._buffer)


class ByteReader:
    """Bounds-checked reader over a buffer; every overrun raises :class:`FormatError`."""

    __slots__ = ("_view", "_pos", "_end", "_context")

    def __init__(self, data: Buffer, context: str = "data") -> None:
        self._view = memoryview(data).cast("B")
        self._pos = 0
        self._end = len(self._view)
        self._context = context

    @property
    def position(self) -> int:
        return self._pos

    @property
    def remaining(self) -> int:
        return self._end - self._pos

    def _take(self, size: int, what: str) -> memoryview:
        start = self._pos
        stop = start + size
        if size < 0 or stop > self._end:
            raise FormatError(
                f"{self._context}: truncated reading {what} "
                f"(need {size} bytes at offset {start}, {self._end - start} left)"
            )
        self._pos = stop
        return self._view[start:stop]

    def u8(self, what: str) -> int:
        return int(_U8.unpack(self._take(1, what))[0])

    def u16(self, what: str) -> int:
        return int(_U16.unpack(self._take(2, what))[0])

    def u32(self, what: str) -> int:
        return int(_U32.unpack(self._take(4, what))[0])

    def u64(self, what: str) -> int:
        return int(_U64.unpack(self._take(8, what))[0])

    def f64(self, what: str) -> float:
        return float(_F64.unpack(self._take(8, what))[0])

    def raw(self, size: int, what: str) -> memoryview:
        return self._take(size, what)

    def array(self, dtype: np.dtype[Any], count: int, what: str) -> np.ndarray:
        """Read ``count`` little-endian items of ``dtype`` as a read-only view (no copy)."""
        little = np.dtype(dtype).newbyteorder("<")
        if count < 0:
            raise FormatError(f"{self._context}: negative element count for {what}")
        size = count * little.itemsize
        return np.frombuffer(self._take(size, what), dtype=little, count=count)

    def string(self, what: str) -> str:
        size = self.u16(f"{what} length")
        try:
            return str(self._take(size, what), "utf-8")
        except UnicodeDecodeError as exc:
            raise FormatError(f"{self._context}: {what} is not valid UTF-8") from exc

    def expect_end(self) -> None:
        if self.remaining:
            raise FormatError(f"{self._context}: {self.remaining} unexpected trailing bytes")
