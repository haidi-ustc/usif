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
from usif.format.binary import (
    BinaryReader,
    BinaryWriter,
    MAX_ATOM_COUNT,
    MAX_COMPRESSED_SIZE,
    MAX_PAYLOAD_SIZE,
    MAX_PROPERTY_SECTION_SIZE,
    MAX_STRING_LENGTH,
    MAX_SYMMETRIC_SITE_COUNT,
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

    def _decompress_data(
        self,
        data: bytes,
        comp_type: CompressionType,
        *,
        max_output_size: int = MAX_PAYLOAD_SIZE,
    ) -> bytes:
        """Decompress data based on compression type with an output size cap."""
        return decompress_data(data, comp_type, max_output_size=max_output_size)

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
        """
        try:
            data = BinaryWriter()

            data.write_u8(structure.structure_type.value, "structure type")
            data.write_u8(structure.storage_mode.value, "storage mode")

            if structure.structure_type == StructureType.MOLECULE:
                if structure.storage_mode == StorageMode.SYMMETRIC:
                    point_group = structure.point_group or "C1"
                    data.write_string_u8(point_group, "point group")
                    data.write_u8(
                        len(structure.point_group_sites), "point-group site count"
                    )
                    for site in structure.point_group_sites:
                        data.write_u8(site.atomic_number, "point-group atomic number")
                        data.write_u16(site.multiplicity, "point-group multiplicity")
                        data.write_f32_tuple3(site.coords, "point-group coords")
                        data.write_f32(site.occupancy, "point-group occupancy")
                else:
                    data.write_u32(len(structure.atom_sites), "atom count")
                    for site in structure.atom_sites:
                        data.write_u8(site.atomic_number, "atomic number")
                        data.write_f32_tuple3(site.coords, "atom coords")
                        data.extend(
                            self._encode_atomic_properties(site.properties, num_atoms=1)
                        )
            else:
                lattice_array = np.asarray(structure.lattice_matrix, dtype=np.float32)
                if lattice_array.shape != (3, 3):
                    raise EncodingError(
                        f"lattice_matrix must have shape (3, 3), got {lattice_array.shape}"
                    )
                data.extend(lattice_array.tobytes())
                data.write_u16(structure.spacegroup, "space group")

                if structure.storage_mode == StorageMode.SYMMETRIC:
                    data.write_u8(len(structure.wyckoff_sites), "wyckoff site count")
                    for site in structure.wyckoff_sites:
                        data.write_u8(site.atomic_number, "wyckoff atomic number")
                        data.write_u16(site.multiplicity, "wyckoff multiplicity")
                        data.write_f32_tuple3(site.coords, "wyckoff coords")
                        data.write_f32(site.occupancy, "wyckoff occupancy")
                else:
                    data.write_u32(len(structure.atom_sites), "atom count")
                    for site in structure.atom_sites:
                        data.write_u8(site.atomic_number, "atomic number")
                        data.write_f32_tuple3(site.coords, "atom coords")
                        data.extend(
                            self._encode_atomic_properties(site.properties, num_atoms=1)
                        )

            struct_prop_data = self._encode_structure_properties(
                structure.structure_properties
            )
            if len(struct_prop_data) > MAX_PROPERTY_SECTION_SIZE:
                raise EncodingError(
                    "Structure property section length "
                    f"{len(struct_prop_data)} exceeds maximum {MAX_PROPERTY_SECTION_SIZE}"
                )
            data.write_u32(len(struct_prop_data), "structure property section length")
            data.extend(struct_prop_data)
            data.write_string_u16(structure.formula, "formula")

            raw_data = bytes(data)
            if len(raw_data) > MAX_PAYLOAD_SIZE:
                raise EncodingError(
                    f"Raw payload size {len(raw_data)} exceeds maximum {MAX_PAYLOAD_SIZE}"
                )
            compressed_data = self._compress_data(raw_data)
            if len(compressed_data) > MAX_COMPRESSED_SIZE:
                raise EncodingError(
                    "Compressed payload size "
                    f"{len(compressed_data)} exceeds maximum {MAX_COMPRESSED_SIZE}"
                )

            header = BinaryWriter()
            header.extend(b"USIF\x00\x00\x00")
            header.write_u8(self.VERSION, "format version")
            header.write_u32(len(raw_data), "raw payload size")
            header.write_u32(len(compressed_data), "compressed payload size")
            header.write_u8(self.compression.value, "compression type")
            header.extend(self._calculate_hash(structure))
            header_bytes = bytes(header)
            if len(header_bytes) > self.HEADER_SIZE:
                raise EncodingError(
                    f"USIF header length {len(header_bytes)} exceeds {self.HEADER_SIZE}"
                )
            return header_bytes.ljust(self.HEADER_SIZE, b"\x00") + compressed_data

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
        """
        try:
            if len(data) < self.HEADER_SIZE:
                raise CorruptedDataError(
                    f"Data too short: {len(data)} < {self.HEADER_SIZE}"
                )

            header = BinaryReader(data[: self.HEADER_SIZE], context="USIF header")
            magic = header.read_bytes(7, "magic")
            if magic != b"USIF\x00\x00\x00":
                raise CorruptedDataError(f"Invalid magic bytes: {magic}")

            version = header.read_u8("format version")
            if version != self.VERSION:
                logger.warning(
                    f"Version mismatch: file version {version}, expected {self.VERSION}"
                )

            raw_size = header.read_u32("raw payload size")
            compressed_size = header.read_u32("compressed payload size")
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
                comp_type = CompressionType(header.read_u8("compression type"))
            except ValueError as e:
                raise CorruptedDataError(f"Invalid compression type in header: {e}") from e

            hash_value = header.read_bytes(32, "geometry hash")

            actual_compressed_size = len(data) - self.HEADER_SIZE
            if actual_compressed_size != compressed_size:
                raise CorruptedDataError(
                    "Compressed payload size mismatch: header says "
                    f"{compressed_size}, file contains {actual_compressed_size}"
                )

            compressed_data = data[self.HEADER_SIZE :]
            payload = self._decompress_data(
                compressed_data, comp_type, max_output_size=raw_size
            )
            if len(payload) != raw_size:
                raise CorruptedDataError(
                    f"Raw payload size mismatch: header says {raw_size}, "
                    f"decoded payload has {len(payload)} bytes"
                )

            reader = BinaryReader(payload, context="USIF payload")
            try:
                structure_type = StructureType(reader.read_u8("structure type"))
                storage_mode = StorageMode(reader.read_u8("storage mode"))
            except ValueError as e:
                raise CorruptedDataError(f"Invalid structure type or storage mode: {e}") from e

            lattice_matrix = None
            spacegroup = 1
            point_group = None
            wyckoff_sites = None
            point_group_sites = None
            atom_sites = None

            if structure_type == StructureType.MOLECULE:
                if storage_mode == StorageMode.SYMMETRIC:
                    point_group = reader.read_string_u8("point group")
                    num_sites = reader.read_u8("point-group site count")
                    if num_sites > MAX_SYMMETRIC_SITE_COUNT:
                        raise CorruptedDataError(
                            f"Point-group site count {num_sites} exceeds maximum "
                            f"{MAX_SYMMETRIC_SITE_COUNT}"
                        )

                    point_group_sites = []
                    for _ in range(num_sites):
                        atomic_num = reader.read_u8("point-group atomic number")
                        mult = reader.read_u16("point-group multiplicity")
                        x, y, z_coord = reader.read_f32_tuple3("point-group coords")
                        occupancy = reader.read_f32("point-group occupancy")
                        point_group_sites.append(
                            PointGroupSite(atomic_num, mult, (x, y, z_coord), occupancy)
                        )
                else:
                    num_atoms = reader.read_u32("atom count")
                    if num_atoms > MAX_ATOM_COUNT:
                        raise CorruptedDataError(
                            f"Atom count {num_atoms} exceeds maximum {MAX_ATOM_COUNT}"
                        )

                    atom_sites = []
                    for _ in range(num_atoms):
                        atomic_num = reader.read_u8("atomic number")
                        x, y, z_coord = reader.read_f32_tuple3("atom coords")
                        atom_props, new_offset = self._decode_atomic_properties(
                            payload, reader.tell(), num_atoms=1
                        )
                        reader.seek(new_offset)
                        atom_sites.append(
                            AtomSite(atomic_num, (x, y, z_coord), atom_props)
                        )
            else:
                lattice_data = reader.read_bytes(36, "lattice matrix")
                lattice_matrix = np.frombuffer(lattice_data, dtype=np.float32).reshape(
                    3, 3
                )

                spacegroup = reader.read_u16("space group")

                if storage_mode == StorageMode.SYMMETRIC:
                    num_sites = reader.read_u8("wyckoff site count")
                    if num_sites > MAX_SYMMETRIC_SITE_COUNT:
                        raise CorruptedDataError(
                            f"Wyckoff site count {num_sites} exceeds maximum "
                            f"{MAX_SYMMETRIC_SITE_COUNT}"
                        )

                    wyckoff_sites = []
                    for _ in range(num_sites):
                        atomic_num = reader.read_u8("wyckoff atomic number")
                        mult = reader.read_u16("wyckoff multiplicity")
                        x, y, z_coord = reader.read_f32_tuple3("wyckoff coords")
                        occupancy = reader.read_f32("wyckoff occupancy")
                        wyckoff_sites.append(
                            WyckoffSite(atomic_num, mult, (x, y, z_coord), occupancy)
                        )
                else:
                    num_atoms = reader.read_u32("atom count")
                    if num_atoms > MAX_ATOM_COUNT:
                        raise CorruptedDataError(
                            f"Atom count {num_atoms} exceeds maximum {MAX_ATOM_COUNT}"
                        )

                    atom_sites = []
                    for _ in range(num_atoms):
                        atomic_num = reader.read_u8("atomic number")
                        x, y, z_coord = reader.read_f32_tuple3("atom coords")
                        atom_props, new_offset = self._decode_atomic_properties(
                            payload, reader.tell(), num_atoms=1
                        )
                        reader.seek(new_offset)
                        atom_sites.append(
                            AtomSite(atomic_num, (x, y, z_coord), atom_props)
                        )

            props_len = reader.read_u32("structure property section length")
            if props_len > MAX_PROPERTY_SECTION_SIZE:
                raise CorruptedDataError(
                    "Structure property section length "
                    f"{props_len} exceeds maximum {MAX_PROPERTY_SECTION_SIZE}"
                )
            props_payload = reader.read_bytes(props_len, "structure property section")
            struct_props, props_offset = self._decode_structure_properties(
                props_payload, 0
            )
            if props_offset != len(props_payload):
                raise CorruptedDataError(
                    "Structure property section was not consumed exactly: "
                    f"decoded {props_offset} of {len(props_payload)} bytes"
                )

            formula_len = reader.read_u16("formula length")
            if formula_len > MAX_STRING_LENGTH:
                raise CorruptedDataError(
                    f"Formula length {formula_len} exceeds maximum {MAX_STRING_LENGTH}"
                )
            formula = reader.read_string(formula_len, "formula")
            reader.assert_consumed("USIF payload")

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
