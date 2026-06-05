"""USIF binary header parsing and writing.

This module owns the fixed-size v5 header layout so the public ``USIF``
facade does not need to know field offsets or packing details.
"""

from dataclasses import dataclass

from usif.constants import CompressionType
from usif.exceptions import CorruptedDataError, EncodingError
from usif.format.binary.limits import MAX_COMPRESSED_SIZE, MAX_PAYLOAD_SIZE
from usif.format.binary.reader import BinaryReader
from usif.format.binary.writer import BinaryWriter

MAGIC = b"USIF\x00\x00\x00"
HEADER_SIZE = 64
HASH_SIZE = 32


@dataclass(frozen=True)
class USIFHeader:
    """Parsed USIF file header."""

    version: int
    raw_size: int
    compressed_size: int
    compression_type: CompressionType
    geometry_hash: bytes

    @classmethod
    def parse(cls, data: bytes) -> "USIFHeader":
        """Parse a fixed-size USIF header from ``data``."""
        if len(data) < HEADER_SIZE:
            raise CorruptedDataError(f"Data too short: {len(data)} < {HEADER_SIZE}")

        reader = BinaryReader(data[:HEADER_SIZE], context="USIF header")
        magic = reader.read_bytes(len(MAGIC), "magic")
        if magic != MAGIC:
            raise CorruptedDataError(f"Invalid magic bytes: {magic}")

        version = reader.read_u8("format version")
        raw_size = reader.read_u32("raw payload size")
        compressed_size = reader.read_u32("compressed payload size")
        if raw_size > MAX_PAYLOAD_SIZE:
            raise CorruptedDataError(
                f"Raw payload size {raw_size} exceeds maximum {MAX_PAYLOAD_SIZE}"
            )
        if compressed_size > MAX_COMPRESSED_SIZE:
            raise CorruptedDataError(
                "Compressed payload size "
                f"{compressed_size} exceeds maximum {MAX_COMPRESSED_SIZE}"
            )

        try:
            compression_type = CompressionType(reader.read_u8("compression type"))
        except ValueError as exc:
            raise CorruptedDataError(
                f"Invalid compression type in header: {exc}"
            ) from exc

        geometry_hash = reader.read_bytes(HASH_SIZE, "geometry hash")
        if len(geometry_hash) != HASH_SIZE:
            raise CorruptedDataError(
                f"Geometry hash length {len(geometry_hash)} != {HASH_SIZE}"
            )

        return cls(
            version=version,
            raw_size=raw_size,
            compressed_size=compressed_size,
            compression_type=compression_type,
            geometry_hash=geometry_hash,
        )

    def to_bytes(self) -> bytes:
        """Serialize the header to the fixed-size padded binary representation."""
        if len(self.geometry_hash) != HASH_SIZE:
            raise EncodingError(
                f"Geometry hash length {len(self.geometry_hash)} != {HASH_SIZE}"
            )
        if self.raw_size > MAX_PAYLOAD_SIZE:
            raise EncodingError(
                f"Raw payload size {self.raw_size} exceeds maximum {MAX_PAYLOAD_SIZE}"
            )
        if self.compressed_size > MAX_COMPRESSED_SIZE:
            raise EncodingError(
                "Compressed payload size "
                f"{self.compressed_size} exceeds maximum {MAX_COMPRESSED_SIZE}"
            )

        writer = BinaryWriter()
        writer.extend(MAGIC)
        writer.write_u8(self.version, "format version")
        writer.write_u32(self.raw_size, "raw payload size")
        writer.write_u32(self.compressed_size, "compressed payload size")
        writer.write_u8(self.compression_type.value, "compression type")
        writer.extend(self.geometry_hash)
        header = bytes(writer)
        if len(header) > HEADER_SIZE:
            raise EncodingError(f"USIF header length {len(header)} exceeds {HEADER_SIZE}")
        return header.ljust(HEADER_SIZE, b"\x00")
