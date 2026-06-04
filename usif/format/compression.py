"""Compression helpers for USIF binary payloads."""

import gzip
import io
from typing import Optional

from usif.constants import CompressionType
from usif.exceptions import CorruptedDataError, DecodingError, EncodingError
from usif.format.binary.limits import MAX_PAYLOAD_SIZE


def compress_data(data: bytes, compression: CompressionType) -> bytes:
    """Compress a raw USIF payload with the requested algorithm."""
    try:
        if compression == CompressionType.GZIP:
            return gzip.compress(data, compresslevel=6)
        return data
    except (OSError, MemoryError) as e:
        raise EncodingError(f"Compression failed: {e}") from e


def _gzip_decompress_limited(data: bytes, max_output_size: int) -> bytes:
    """Decompress gzip data without allowing unbounded output growth."""
    output = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as gz:
            while True:
                chunk = gz.read(min(1024 * 1024, max_output_size + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > max_output_size:
                    raise CorruptedDataError(
                        f"Decompressed payload exceeds maximum {max_output_size} bytes"
                    )
    except CorruptedDataError:
        raise
    except gzip.BadGzipFile as e:
        raise CorruptedDataError(f"Corrupted gzip data: {e}") from e
    except EOFError as e:
        raise CorruptedDataError(f"Truncated gzip data: {e}") from e
    except OSError as e:
        raise CorruptedDataError(f"Corrupted gzip data: {e}") from e
    return bytes(output)


def decompress_data(
    data: bytes,
    compression: CompressionType,
    *,
    max_output_size: Optional[int] = MAX_PAYLOAD_SIZE,
) -> bytes:
    """Decompress a USIF payload using the algorithm stored in the header.

    Args:
        data: Compressed bytes.
        compression: Compression algorithm from the USIF header.
        max_output_size: Maximum allowed uncompressed payload size. ``None`` disables
            the explicit cap and should only be used for trusted data.
    """
    try:
        limit = MAX_PAYLOAD_SIZE if max_output_size is None else max_output_size
        if compression == CompressionType.GZIP:
            return _gzip_decompress_limited(data, limit)
        if len(data) > limit:
            raise CorruptedDataError(
                f"Uncompressed payload size {len(data)} exceeds maximum {limit} bytes"
            )
        return data
    except CorruptedDataError:
        raise
    except Exception as e:
        raise DecodingError(f"Decompression failed: {e}") from e
