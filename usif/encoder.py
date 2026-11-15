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
from usif.fileio import atomic_write_bytes
from usif.format import (
    calculate_geometry_hash,
    calculate_record_hash,
    compress_data,
    decompress_data,
)
from usif.format.binary.structure_codec import SUPPORTED_FORMAT_VERSIONS
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
        return self._frame(structure, self._encode_body(structure))

    def encode_with_record_hash(self, structure: USIFStructure) -> Tuple[bytes, str]:
        """Encode ``structure`` and return ``(record_bytes, record_hash_hex)``.

        The hash is computed from the stored form (see :meth:`canonicalize`),
        so it equals the hash of the structure decoded from these bytes.
        """
        raw_payload = self._encode_body(structure)
        stored = self._decode_body(raw_payload)
        return self._frame(structure, raw_payload), calculate_record_hash(stored).hex()

    def canonicalize(self, structure: USIFStructure) -> USIFStructure:
        """Return ``structure`` exactly as it reads back after encode/decode.

        Stored records use float32 coordinates and JSON custom values, so a
        freshly built structure can differ from its stored form in the last
        bits or in container types (tuple vs list). Hashing the canonical form
        makes record identity survive a save/load round trip.
        """
        return self._decode_body(self._encode_body(structure))

    def _encode_body(self, structure: USIFStructure) -> bytes:
        try:
            return self.structure_codec.encode_body(structure)
        except (EncodingError, ValidationError):
            raise
        except (ValueError, TypeError) as exc:
            raise EncodingError(f"Failed to encode structure: {exc}") from exc
        except Exception as exc:
            raise EncodingError(f"Unexpected error during encoding: {exc}") from exc

    def _decode_body(self, raw_payload: bytes) -> USIFStructure:
        try:
            return self.structure_codec.decode_body(raw_payload)
        except (DecodingError, CorruptedDataError, ValidationError):
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise DecodingError(f"Failed to decode structure: {exc}") from exc

    def _frame(self, structure: USIFStructure, raw_payload: bytes) -> bytes:
        """Compress ``raw_payload`` and prepend the record header."""
        try:
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
            if header.version not in SUPPORTED_FORMAT_VERSIONS:
                raise CorruptedDataError(
                    f"Unsupported USIF record version {header.version}; "
                    f"supported: {sorted(SUPPORTED_FORMAT_VERSIONS)}"
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

            structure = self.structure_codec.decode_body(raw_payload, header.version)
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
        """Return the full record hash of ``structure`` in its stored form."""
        return calculate_record_hash(self.canonicalize(structure)).hex()

    def save(self, structure: USIFStructure, filename: Union[str, Path]) -> None:
        """Save a structure to a USIF binary file.

        The record is fully encoded before the destination is touched and is
        then written atomically, so a failure never damages an existing file.
        """
        data = self.encode(structure)
        try:
            atomic_write_bytes(filename, data)
        except OSError as exc:
            raise StorageError(f"Failed to save structure to {filename}: {exc}") from exc

    def load(self, filename: Union[str, Path]) -> USIFStructure:
        """Load a structure from a USIF binary file."""
        try:
            with open(filename, "rb") as handle:
                structure, _ = self.decode(handle.read())
            return structure
        except (IOError, FileNotFoundError) as exc:
            raise StorageError(f"Failed to load structure from {filename}: {exc}") from exc
