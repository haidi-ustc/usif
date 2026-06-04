#!/usr/bin/env python3
"""
USIF Encoder/Decoder Module

This module provides the core encoding and decoding functionality for the USIF format.
The USIF class handles binary serialization of structures with compression support.

Main Class:
    USIF: Encoder/decoder for USIF binary format

Features:
    - Binary encoding/decoding of USIF structures
    - Multiple compression algorithms (GZIP, LZMA, BZIP2)
    - Hash-based integrity checking
    - Efficient property serialization

Usage:
    >>> from usif import USIF, USIFStructure
    >>>
    >>> # Encode a structure
    >>> encoder = USIF()
    >>> structure = USIFStructure(...)
    >>> binary_data = encoder.encode(structure)
    >>>
    >>> # Decode binary data
    >>> decoded_structure = encoder.decode(binary_data)
    >>>
    >>> # Save/load with compression
    >>> structure.save('file.usif', compression=CompressionType.GZIP)
    >>> loaded = USIFStructure.load('file.usif')

See Also:
    - USIFStructure: Structure representation
    - PropertySerializer: Property serialization
"""

import logging
import struct
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np

from usif.constants import BinaryFormat, CompressionType, StorageMode, StructureType
from usif.exceptions import (
    CorruptedDataError,
    DecodingError,
    IntegrityError,
    EncodingError,
    StorageError,
    ValidationError,
)
from usif.format import (
    PropertyCodec,
    calculate_geometry_hash,
    calculate_record_hash,
    calculate_structure_hash,
    compress_data,
    decompress_data,
)
from usif.properties.atomic import AtomicProperties
from usif.properties.registry import PropertyRegistry
from usif.properties.structure import StructureProperties
from usif.structures.sites import AtomSite, PointGroupSite, WyckoffSite
from usif.structures.structure import USIFStructure
from usif.version import FORMAT_VERSION

logger = logging.getLogger(__name__)


class USIF:
    """USIF (Universal Structure Interchange Format) Encoder/Decoder"""

    VERSION = FORMAT_VERSION  # Use global format version
    HEADER_SIZE = 64

    def __init__(
        self,
        compression: CompressionType = CompressionType.GZIP,
        property_registry=PropertyRegistry,
        strict_integrity: bool = True,
    ):
        """
        Initialize USIF encoder/decoder

        Args:
            compression: Compression algorithm to use (default: GZIP)

        Example:
            >>> encoder = USIF(compression=CompressionType.GZIP)
            >>> encoder = USIF(compression=CompressionType.NONE)  # No compression
        """
        self.compression = compression
        self.property_registry = property_registry
        self.strict_integrity = strict_integrity
        self.property_codec = PropertyCodec(property_registry)

    @staticmethod
    def _json_default(value):
        """Convert common scientific Python values to JSON-compatible data."""
        return PropertyCodec._json_default(value)

    @staticmethod
    def _encode_custom_value(value) -> bytes:
        return PropertyCodec.encode_custom_value(value)

    @staticmethod
    def _decode_custom_value(value_str):
        return PropertyCodec.decode_custom_value(value_str)

    def _calculate_hash(self, structure: USIFStructure) -> bytes:
        """Calculate historical geometry SHA-256 hash of structure."""
        return calculate_structure_hash(structure)

    def _calculate_record_hash(self, structure: USIFStructure) -> bytes:
        """Calculate record SHA-256 hash of structure and properties."""
        return calculate_record_hash(structure)

    def _compress_data(self, data: bytes) -> bytes:
        """Compress data based on compression type."""
        return compress_data(data, self.compression)

    def _decompress_data(self, data: bytes, comp_type: CompressionType) -> bytes:
        """Decompress data based on compression type."""
        return decompress_data(data, comp_type)

    def _encode_atomic_properties(
        self, props: AtomicProperties, num_atoms: Optional[int] = None
    ) -> bytes:
        """Encode atomic properties using modular system."""
        return self.property_codec.encode_atomic_properties(props, num_atoms=num_atoms)

    def _decode_atomic_properties(
        self, data: bytes, offset: int, num_atoms: Optional[int] = None
    ) -> Tuple[AtomicProperties, int]:
        """Decode atomic properties using modular system."""
        return self.property_codec.decode_atomic_properties(
            data, offset, num_atoms=num_atoms
        )

    def _encode_structure_properties(self, props: StructureProperties) -> bytes:
        """Encode structure properties using modular system."""
        return self.property_codec.encode_structure_properties(props)

    def _decode_structure_properties(
        self, data: bytes, offset: int
    ) -> Tuple[StructureProperties, int]:
        """Decode structure properties using modular system."""
        return self.property_codec.decode_structure_properties(data, offset)

    def encode(self, structure: USIFStructure) -> bytes:
        """
        Encode USIFStructure to binary format

        Converts a USIFStructure object into a binary byte string that can be
        saved to disk or transmitted. The encoding includes the structure data,
        properties, and metadata with optional compression.

        Args:
            structure: USIFStructure instance to encode

        Returns:
            bytes: Encoded binary data (compressed if compression is enabled)

        Raises:
            EncodingError: If encoding fails due to invalid data or serialization errors

        Example:
            >>> encoder = USIF()
            >>> structure = USIFStructure(...)
            >>> binary_data = encoder.encode(structure)
            >>> len(binary_data)  # Size of encoded data
        """
        try:
            data = bytearray()

            data.extend(struct.pack(BinaryFormat.UINT8, structure.structure_type.value))
            data.extend(struct.pack(BinaryFormat.UINT8, structure.storage_mode.value))

            if structure.structure_type == StructureType.MOLECULE:
                if structure.storage_mode == StorageMode.SYMMETRIC:
                    point_group = structure.point_group or "C1"
                    pg_bytes = point_group.encode("utf-8")
                    data.extend(struct.pack(BinaryFormat.UINT8, len(pg_bytes)))
                    data.extend(pg_bytes)

                    data.extend(
                        struct.pack(
                            BinaryFormat.UINT8, len(structure.point_group_sites)
                        )
                    )
                    for site in structure.point_group_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.UINT16, site.multiplicity))
                        data.extend(
                            struct.pack(
                                BinaryFormat.array(BinaryFormat.FLOAT32, 3),
                                *site.coords,
                            )
                        )
                        data.extend(struct.pack(BinaryFormat.FLOAT32, site.occupancy))
                else:
                    data.extend(
                        struct.pack(BinaryFormat.UINT32, len(structure.atom_sites))
                    )
                    for site in structure.atom_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(
                            struct.pack(
                                BinaryFormat.array(BinaryFormat.FLOAT32, 3),
                                *site.coords,
                            )
                        )
                        atom_prop_data = self._encode_atomic_properties(
                            site.properties, num_atoms=1
                        )
                        data.extend(atom_prop_data)
            else:
                lattice_data = structure.lattice_matrix.astype(np.float32).tobytes()
                data.extend(lattice_data)
                data.extend(struct.pack(BinaryFormat.UINT16, structure.spacegroup))

                if structure.storage_mode == StorageMode.SYMMETRIC:
                    data.extend(
                        struct.pack(BinaryFormat.UINT8, len(structure.wyckoff_sites))
                    )
                    for site in structure.wyckoff_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.UINT16, site.multiplicity))
                        data.extend(
                            struct.pack(
                                BinaryFormat.array(BinaryFormat.FLOAT32, 3),
                                *site.coords,
                            )
                        )
                        data.extend(struct.pack(BinaryFormat.FLOAT32, site.occupancy))
                else:
                    data.extend(
                        struct.pack(BinaryFormat.UINT32, len(structure.atom_sites))
                    )
                    for site in structure.atom_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(
                            struct.pack(
                                BinaryFormat.array(BinaryFormat.FLOAT32, 3),
                                *site.coords,
                            )
                        )
                        atom_prop_data = self._encode_atomic_properties(
                            site.properties, num_atoms=1
                        )
                        data.extend(atom_prop_data)

            struct_prop_data = self._encode_structure_properties(
                structure.structure_properties
            )
            data.extend(struct.pack(BinaryFormat.UINT32, len(struct_prop_data)))
            data.extend(struct_prop_data)

            formula_bytes = structure.formula.encode("utf-8")
            data.extend(struct.pack(BinaryFormat.UINT16, len(formula_bytes)))
            data.extend(formula_bytes)

            raw_data = bytes(data)
            compressed_data = self._compress_data(raw_data)

            header = bytearray(self.HEADER_SIZE)
            header[0:7] = b"USIF\x00\x00\x00"
            header[7:8] = struct.pack(BinaryFormat.UINT8, self.VERSION)
            header[8:12] = struct.pack(BinaryFormat.UINT32, len(raw_data))
            header[12:16] = struct.pack(BinaryFormat.UINT32, len(compressed_data))
            header[16:17] = struct.pack(BinaryFormat.UINT8, self.compression.value)

            hash_value = self._calculate_hash(structure)
            header[17:49] = hash_value

            return bytes(header) + compressed_data

        except (EncodingError, ValidationError):
            raise
        except (ValueError, TypeError, struct.error) as e:
            raise EncodingError(f"Failed to encode structure: {e}") from e
        except Exception as e:
            raise EncodingError(f"Unexpected error during encoding: {e}") from e

    def decode(self, data: bytes) -> Tuple[USIFStructure, bytes]:
        """
        Decode binary data to USIFStructure

        Converts binary encoded data back into a USIFStructure object.
        Handles decompression, validation, and reconstruction of the structure
        with all its properties.

        Args:
            data: Encoded binary data (must include header)

        Returns:
            Tuple[USIFStructure, bytes]: Decoded structure and its hash value

        Raises:
            DecodingError: If decoding fails due to invalid format or data
            CorruptedDataError: If data is corrupted or incomplete
            ValidationError: If decoded structure fails validation

        Example:
            >>> encoder = USIF()
            >>> binary_data = encoder.encode(structure)
            >>> decoded_structure, hash_value = encoder.decode(binary_data)
            >>> print(f"Structure hash: {hash_value.hex()}")
        """
        try:
            if len(data) < self.HEADER_SIZE:
                raise CorruptedDataError(
                    f"Data too short: {len(data)} < {self.HEADER_SIZE}"
                )

            magic = data[0:7]
            if magic != b"USIF\x00\x00\x00":
                raise CorruptedDataError(f"Invalid magic bytes: {magic}")

            version = struct.unpack(BinaryFormat.UINT8, data[7:8])[0]
            if version != self.VERSION:
                logger.warning(
                    f"Version mismatch: file version {version}, expected {self.VERSION}"
                )

            struct.unpack(BinaryFormat.UINT32, data[8:12])[0]  # raw_size
            compressed_size = struct.unpack(BinaryFormat.UINT32, data[12:16])[0]
            comp_type = CompressionType(
                struct.unpack(BinaryFormat.UINT8, data[16:17])[0]
            )
            hash_value = data[17:49]

            compressed_data = data[
                self.HEADER_SIZE : self.HEADER_SIZE + compressed_size
            ]
            data = self._decompress_data(compressed_data, comp_type)

            offset = 0
            structure_type = StructureType(
                struct.unpack(BinaryFormat.UINT8, data[offset : offset + 1])[0]
            )
            offset += 1
            storage_mode = StorageMode(
                struct.unpack(BinaryFormat.UINT8, data[offset : offset + 1])[0]
            )
            offset += 1

            lattice_matrix = None
            spacegroup = 1
            point_group = None
            wyckoff_sites = None
            point_group_sites = None
            atom_sites = None

            if structure_type == StructureType.MOLECULE:
                if storage_mode == StorageMode.SYMMETRIC:
                    pg_len = struct.unpack(
                        BinaryFormat.UINT8, data[offset : offset + 1]
                    )[0]
                    offset += 1
                    point_group = data[offset : offset + pg_len].decode("utf-8")
                    offset += pg_len

                    num_sites = struct.unpack(
                        BinaryFormat.UINT8, data[offset : offset + 1]
                    )[0]
                    offset += 1

                    point_group_sites = []
                    for _ in range(num_sites):
                        atomic_num = struct.unpack(
                            BinaryFormat.UINT8, data[offset : offset + 1]
                        )[0]
                        mult = struct.unpack(
                            BinaryFormat.UINT16, data[offset + 1 : offset + 3]
                        )[0]
                        x, y, z_coord = struct.unpack(
                            BinaryFormat.array(BinaryFormat.FLOAT32, 3),
                            data[offset + 3 : offset + 15],
                        )
                        occupancy = struct.unpack(
                            BinaryFormat.FLOAT32, data[offset + 15 : offset + 19]
                        )[0]
                        offset += 19
                        point_group_sites.append(
                            PointGroupSite(atomic_num, mult, (x, y, z_coord), occupancy)
                        )
                else:
                    num_atoms = struct.unpack(
                        BinaryFormat.UINT32, data[offset : offset + 4]
                    )[0]
                    offset += 4

                    atom_sites = []
                    for _ in range(num_atoms):
                        atomic_num = struct.unpack(
                            BinaryFormat.UINT8, data[offset : offset + 1]
                        )[0]
                        x, y, z_coord = struct.unpack(
                            BinaryFormat.array(BinaryFormat.FLOAT32, 3),
                            data[offset + 1 : offset + 13],
                        )
                        offset += 13
                        atom_props, offset = self._decode_atomic_properties(
                            data, offset, num_atoms=1
                        )
                        atom_sites.append(
                            AtomSite(atomic_num, (x, y, z_coord), atom_props)
                        )
            else:
                lattice_data = data[offset : offset + 36]
                lattice_matrix = np.frombuffer(lattice_data, dtype=np.float32).reshape(
                    3, 3
                )
                offset += 36

                spacegroup = struct.unpack(
                    BinaryFormat.UINT16, data[offset : offset + 2]
                )[0]
                offset += 2

                if storage_mode == StorageMode.SYMMETRIC:
                    num_sites = struct.unpack(
                        BinaryFormat.UINT8, data[offset : offset + 1]
                    )[0]
                    offset += 1

                    wyckoff_sites = []
                    for _ in range(num_sites):
                        atomic_num = struct.unpack(
                            BinaryFormat.UINT8, data[offset : offset + 1]
                        )[0]
                        mult = struct.unpack(
                            BinaryFormat.UINT16, data[offset + 1 : offset + 3]
                        )[0]
                        x, y, z_coord = struct.unpack(
                            BinaryFormat.array(BinaryFormat.FLOAT32, 3),
                            data[offset + 3 : offset + 15],
                        )
                        occupancy = struct.unpack(
                            BinaryFormat.FLOAT32, data[offset + 15 : offset + 19]
                        )[0]
                        offset += 19
                        wyckoff_sites.append(
                            WyckoffSite(atomic_num, mult, (x, y, z_coord), occupancy)
                        )
                else:
                    num_atoms = struct.unpack(
                        BinaryFormat.UINT32, data[offset : offset + 4]
                    )[0]
                    offset += 4

                    atom_sites = []
                    for _ in range(num_atoms):
                        atomic_num = struct.unpack(
                            BinaryFormat.UINT8, data[offset : offset + 1]
                        )[0]
                        x, y, z_coord = struct.unpack(
                            BinaryFormat.array(BinaryFormat.FLOAT32, 3),
                            data[offset + 1 : offset + 13],
                        )
                        offset += 13
                        atom_props, offset = self._decode_atomic_properties(
                            data, offset, num_atoms=1
                        )
                        atom_sites.append(
                            AtomSite(atomic_num, (x, y, z_coord), atom_props)
                        )

            struct.unpack(BinaryFormat.UINT32, data[offset : offset + 4])[
                0
            ]  # props_len
            offset += 4
            struct_props, offset = self._decode_structure_properties(data, offset)

            formula_len = struct.unpack(BinaryFormat.UINT16, data[offset : offset + 2])[
                0
            ]
            offset += 2
            formula = data[offset : offset + formula_len].decode("utf-8")

            if structure_type == StructureType.MOLECULE:
                structure = USIFStructure(
                    structure_type=structure_type,
                    storage_mode=storage_mode,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    atom_sites=atom_sites,
                    structure_properties=struct_props,
                    formula=formula,
                )
            else:
                structure = USIFStructure(
                    structure_type=structure_type,
                    lattice_matrix=lattice_matrix,
                    spacegroup=spacegroup,
                    storage_mode=storage_mode,
                    wyckoff_sites=wyckoff_sites,
                    atom_sites=atom_sites,
                    structure_properties=struct_props,
                    formula=formula,
                )

            expected_hash = self._calculate_hash(structure)
            if hash_value != expected_hash:
                message = (
                    "USIF integrity check failed: header geometry hash "
                    f"{hash_value.hex()} != decoded geometry hash {expected_hash.hex()}"
                )
                if self.strict_integrity:
                    raise IntegrityError(message)
                logger.warning(message)

            return structure, hash_value

        except (struct.error, UnicodeDecodeError) as e:
            raise DecodingError(f"Failed to decode data: {e}") from e
        except (DecodingError, CorruptedDataError, ValidationError):
            raise
        except (ValueError, TypeError, KeyError) as e:
            raise DecodingError(f"Failed to decode structure: {e}") from e
        except Exception as e:
            raise DecodingError(f"Unexpected error during decoding: {e}") from e

    def get_structure_hash(self, structure: USIFStructure) -> str:
        """
        Calculate and return hexadecimal geometry hash of structure

        Computes a SHA-256 hash of the structure's geometry data (type, mode,
        lattice, sites) for geometry identification. Use get_record_hash() for
        container deduplication because this hash intentionally excludes properties.

        Args:
            structure: USIFStructure to hash

        Returns:
            str: Hexadecimal representation of the structure hash (64 characters)

        Example:
            >>> encoder = USIF()
            >>> hash_str = encoder.get_structure_hash(structure)
            >>> print(f"Structure ID: {hash_str[:16]}...")
        """
        return self._calculate_hash(structure).hex()

    def get_geometry_hash(self, structure: USIFStructure) -> str:
        """Return the geometry-only hash of a structure."""
        return calculate_geometry_hash(structure).hex()

    def get_record_hash(self, structure: USIFStructure) -> str:
        """Return the full record hash including formula and properties."""
        return self._calculate_record_hash(structure).hex()

    def save(self, structure: USIFStructure, filename: Union[str, Path]) -> None:
        """
        Save structure to file

        Encodes a USIFStructure and writes it to a file. The file format includes
        header, compressed data, and metadata.

        Args:
            structure: USIFStructure to save
            filename: Output file path (typically with .usif extension)

        Raises:
            StorageError: If file I/O fails

        Example:
            >>> encoder = USIF()
            >>> encoder.save(structure, "my_structure.usif")
        """
        try:
            with open(filename, "wb") as f:
                f.write(self.encode(structure))
        except IOError as e:
            raise StorageError(f"Failed to save structure to {filename}: {e}") from e

    def load(self, filename: Union[str, Path]) -> USIFStructure:
        """
        Load structure from file

        Reads and decodes a USIFStructure from a file. The file must be in
        USIF binary format.

        Args:
            filename: Input file path (typically with .usif extension)

        Returns:
            USIFStructure: Decoded structure from file

        Raises:
            StorageError: If file I/O fails or file not found
            DecodingError: If file format is invalid

        Example:
            >>> encoder = USIF()
            >>> structure = encoder.load("my_structure.usif")
        """
        try:
            with open(filename, "rb") as f:
                structure, _ = self.decode(f.read())
            return structure
        except (IOError, FileNotFoundError) as e:
            raise StorageError(f"Failed to load structure from {filename}: {e}") from e
