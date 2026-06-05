#!/usr/bin/env python3
"""Public USIF binary encoder/decoder API.

Header parsing, payload structure encoding, property encoding, compression, and
integrity checks live in focused ``usif.format.binary`` modules. ``USIF`` is the
stable user-facing codec entry point.
"""

from pathlib import Path
from typing import Optional, Tuple, Union

from usif.constants import CompressionType
from usif.exceptions import (
    CorruptedDataError,
    DecodingError,
    EncodingError,
    StorageError,
    ValidationError,
)
from usif.format import (
    calculate_geometry_hash,
    calculate_record_hash,
    compress_data,
    decompress_data,
)
from usif.format.binary import (
    HEADER_SIZE,
    MAX_COMPRESSED_SIZE,
    MAX_PAYLOAD_SIZE,
    PropertyCodec,
    StructureBinaryCodec,
    USIFHeader,
    validate_geometry_hash,
)
from usif.properties.atomic import AtomicProperties
from usif.properties.structure import StructureProperties
from usif.structures.structure import USIFStructure
from usif.version import FORMAT_VERSION



class USIF:
    """USIF (Universal Structure Interchange Format) encoder/decoder."""

    VERSION = FORMAT_VERSION
    HEADER_SIZE = HEADER_SIZE

    def __init__(
        self,
        compression: CompressionType = CompressionType.GZIP,
        property_registry=None,
        strict_integrity: bool = True,
    ):
        self.compression = compression
        self.property_registry = property_registry
        self.strict_integrity = strict_integrity
        self.structure_codec = StructureBinaryCodec(property_registry)
        self.property_codec = self.structure_codec.property_codec

    def _encode_atomic_properties(
        self, props: AtomicProperties, num_atoms: Optional[int] = None
    ) -> bytes:
        return self.structure_codec.encode_atomic_properties(props, num_atoms=num_atoms)

    def _decode_atomic_properties(
        self, data: bytes, offset: int, num_atoms: Optional[int] = None
    ) -> Tuple[AtomicProperties, int]:
        return self.structure_codec.decode_atomic_properties(
            data, offset, num_atoms=num_atoms
        )

    def _encode_structure_properties(self, props: StructureProperties) -> bytes:
        return self.structure_codec.encode_structure_properties(props)

    def _decode_structure_properties(
        self, data: bytes, offset: int
    ) -> Tuple[StructureProperties, int]:
        return self.structure_codec.decode_structure_properties(data, offset)

    def encode(self, structure: USIFStructure) -> bytes:
        """Encode a :class:`USIFStructure` to USIF binary bytes."""
        try:
            raw_payload = self.structure_codec.encode_body(structure)
            compressed_payload = compress_data(raw_payload, self.compression)
            if len(compressed_payload) > MAX_COMPRESSED_SIZE:
                raise EncodingError(
                    "Compressed payload size "
                    f"{len(compressed_payload)} exceeds maximum {MAX_COMPRESSED_SIZE}"
                )

            header = USIFHeader(
                version=self.VERSION,
                raw_size=len(raw_payload),
                compressed_size=len(compressed_payload),
                compression_type=self.compression,
                geometry_hash=calculate_geometry_hash(structure),
            )
            return header.to_bytes() + compressed_payload
        except (EncodingError, ValidationError):
            raise
        except (ValueError, TypeError) as exc:
            raise EncodingError(f"Failed to encode structure: {exc}") from exc
        except Exception as exc:
            raise EncodingError(f"Unexpected error during encoding: {exc}") from exc

    def decode(self, data: bytes) -> Tuple[USIFStructure, bytes]:
        """Decode USIF binary bytes into ``(structure, geometry_hash)``."""
        try:
            header = USIFHeader.parse(data)
            if header.version != self.VERSION:
                raise CorruptedDataError(
                    f"Unsupported USIF record version {header.version}; expected {self.VERSION}"
                )

            actual_compressed_size = len(data) - self.HEADER_SIZE
            if actual_compressed_size != header.compressed_size:
                raise CorruptedDataError(
                    "Compressed payload size mismatch: header says "
                    f"{header.compressed_size}, file contains {actual_compressed_size}"
                )

            compressed_payload = data[self.HEADER_SIZE :]
            raw_payload = decompress_data(
                compressed_payload,
                header.compression_type,
                max_output_size=header.raw_size,
            )
            if len(raw_payload) != header.raw_size:
                raise CorruptedDataError(
                    f"Raw payload size mismatch: header says {header.raw_size}, "
                    f"decoded payload has {len(raw_payload)} bytes"
                )

            structure = self.structure_codec.decode_body(raw_payload)
            validate_geometry_hash(
                structure, header.geometry_hash, strict=self.strict_integrity
            )
            return structure, header.geometry_hash
        except (DecodingError, CorruptedDataError, ValidationError):
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise DecodingError(f"Failed to decode structure: {exc}") from exc
        except Exception as exc:
            raise DecodingError(f"Unexpected error during decoding: {exc}") from exc

    def get_geometry_hash(self, structure: USIFStructure) -> str:
        """Return the geometry-only hash of a structure."""
        return calculate_geometry_hash(structure).hex()

    def get_record_hash(self, structure: USIFStructure) -> str:
        """Return the full record hash including formula and properties."""
        return calculate_record_hash(structure).hex()

    def save(self, structure: USIFStructure, filename: Union[str, Path]) -> None:
        """Save a structure to a USIF binary file."""
        try:
            with open(filename, "wb") as handle:
                handle.write(self.encode(structure))
        except IOError as exc:
            raise StorageError(f"Failed to save structure to {filename}: {exc}") from exc

    def load(self, filename: Union[str, Path]) -> USIFStructure:
        """Load a structure from a USIF binary file."""
        try:
            with open(filename, "rb") as handle:
                structure, _ = self.decode(handle.read())
            return structure
        except (IOError, FileNotFoundError) as exc:
            raise StorageError(f"Failed to load structure from {filename}: {exc}") from exc
