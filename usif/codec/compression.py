"""Payload compression codecs.

Each codec has a stable one-byte id stored in record headers. Decompression
is always bounded by the size the header declares, so a malicious or
corrupted payload cannot expand into an unbounded allocation.

Third-party codecs can be added with :func:`register`.
"""

from __future__ import annotations

import lzma
import zlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from usif.errors import FormatError, MissingDependencyError, ValidationError

__all__ = ["Compressor", "available", "get", "register"]


@dataclass(frozen=True)
class Compressor:
    """A compression codec: ``compress(data, level)`` and bounded ``decompress``."""

    id: int
    name: str
    compress: Callable[[bytes, Optional[int]], bytes]
    decompress: Callable[[bytes, int], bytes]  # (data, exact_output_size) -> data


def _check_size(output: bytes, expected: int, name: str) -> bytes:
    if len(output) != expected:
        raise FormatError(f"{name} payload expands to {len(output)} bytes, header says {expected}")
    return output


def _zlib_compress(data: bytes, level: Optional[int]) -> bytes:
    return zlib.compress(data, 6 if level is None else level)


def _zlib_decompress(data: bytes, size: int) -> bytes:
    inflater = zlib.decompressobj()
    try:
        output = inflater.decompress(data, size)
    except zlib.error as exc:
        raise FormatError(f"zlib payload is corrupt: {exc}") from exc
    if inflater.unconsumed_tail or not inflater.eof:
        raise FormatError("zlib payload is larger than declared or truncated")
    return _check_size(output, size, "zlib")


def _lzma_compress(data: bytes, level: Optional[int]) -> bytes:
    return lzma.compress(data, format=lzma.FORMAT_XZ, preset=6 if level is None else level)


def _lzma_decompress(data: bytes, size: int) -> bytes:
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    try:
        output = decoder.decompress(data, size)
    except lzma.LZMAError as exc:
        raise FormatError(f"lzma payload is corrupt: {exc}") from exc
    if not decoder.eof:
        raise FormatError("lzma payload is larger than declared or truncated")
    return _check_size(output, size, "lzma")


def _zstd_module() -> Any:
    try:
        import zstandard
    except ImportError as exc:
        raise MissingDependencyError("zstandard", "zstd compression", extra="zstd") from exc
    return zstandard


def _zstd_compress(data: bytes, level: Optional[int]) -> bytes:
    zstandard = _zstd_module()
    return bytes(zstandard.ZstdCompressor(level=3 if level is None else level).compress(data))


def _zstd_decompress(data: bytes, size: int) -> bytes:
    zstandard = _zstd_module()
    try:
        output = zstandard.ZstdDecompressor().decompress(data, max_output_size=size)
    except zstandard.ZstdError as exc:
        raise FormatError(f"zstd payload is corrupt: {exc}") from exc
    return _check_size(bytes(output), size, "zstd")


def _identity(data: bytes, level: Optional[int]) -> bytes:
    return data


def _identity_decompress(data: bytes, size: int) -> bytes:
    return _check_size(data, size, "uncompressed")


_BY_ID: Dict[int, Compressor] = {}
_BY_NAME: Dict[str, Compressor] = {}


def register(compressor: Compressor) -> None:
    """Register a codec. Ids 0-63 are reserved for USIF itself."""
    if not 0 <= compressor.id <= 255:
        raise ValidationError("compressor id must fit in one byte")
    if compressor.id in _BY_ID or compressor.name in _BY_NAME:
        raise ValidationError(f"compressor {compressor.name!r}/{compressor.id} already registered")
    _BY_ID[compressor.id] = compressor
    _BY_NAME[compressor.name] = compressor


def get(key: int | str) -> Compressor:
    """Look a codec up by id or name."""
    table = _BY_ID if isinstance(key, int) else _BY_NAME
    try:
        return table[key]  # type: ignore[index]
    except KeyError:
        if isinstance(key, int):
            raise FormatError(f"unknown compression id {key}") from None
        raise ValidationError(f"unknown compression {key!r}; known: {sorted(_BY_NAME)}") from None


def available() -> list[str]:
    return sorted(_BY_NAME)


register(Compressor(0, "none", _identity, _identity_decompress))
register(Compressor(1, "zlib", _zlib_compress, _zlib_decompress))
register(Compressor(2, "lzma", _lzma_compress, _lzma_decompress))
register(Compressor(3, "zstd", _zstd_compress, _zstd_decompress))
