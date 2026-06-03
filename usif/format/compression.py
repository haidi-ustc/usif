"""Compression helpers for USIF binary payloads."""

import gzip

from usif.constants import CompressionType
from usif.exceptions import CorruptedDataError, DecodingError, EncodingError


def compress_data(data: bytes, compression: CompressionType) -> bytes:
    """Compress a raw USIF payload with the requested algorithm."""
    try:
        if compression == CompressionType.GZIP:
            return gzip.compress(data, compresslevel=6)
        return data
    except (OSError, MemoryError) as e:
        raise EncodingError(f"Compression failed: {e}") from e


def decompress_data(data: bytes, compression: CompressionType) -> bytes:
    """Decompress a USIF payload using the algorithm stored in the header."""
    try:
        if compression == CompressionType.GZIP:
            return gzip.decompress(data)
        return data
    except gzip.BadGzipFile as e:
        raise CorruptedDataError(f"Corrupted gzip data: {e}") from e
    except Exception as e:
        raise DecodingError(f"Decompression failed: {e}") from e
