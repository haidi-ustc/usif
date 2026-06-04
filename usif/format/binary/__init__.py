"""Defensive binary helpers for USIF codecs."""

from usif.format.binary.header import HEADER_SIZE, USIFHeader
from usif.format.binary.integrity import validate_geometry_hash
from usif.format.binary.limits import (
    MAX_ATOM_COUNT,
    MAX_COMPRESSED_SIZE,
    MAX_CUSTOM_PROPERTY_COUNT,
    MAX_KNOWN_PROPERTY_COUNT,
    MAX_PAYLOAD_SIZE,
    MAX_PROPERTY_SECTION_SIZE,
    MAX_PROPERTY_VALUE_SIZE,
    MAX_STRING_LENGTH,
    MAX_SYMMETRIC_SITE_COUNT,
)
from usif.format.binary.property_codec import PropertyCodec
from usif.format.binary.reader import BinaryReader
from usif.format.binary.structure_codec import StructureBinaryCodec
from usif.format.binary.writer import BinaryWriter

__all__ = [
    "BinaryReader",
    "BinaryWriter",
    "HEADER_SIZE",
    "USIFHeader",
    "PropertyCodec",
    "StructureBinaryCodec",
    "validate_geometry_hash",
    "MAX_ATOM_COUNT",
    "MAX_COMPRESSED_SIZE",
    "MAX_CUSTOM_PROPERTY_COUNT",
    "MAX_KNOWN_PROPERTY_COUNT",
    "MAX_PAYLOAD_SIZE",
    "MAX_PROPERTY_SECTION_SIZE",
    "MAX_PROPERTY_VALUE_SIZE",
    "MAX_STRING_LENGTH",
    "MAX_SYMMETRIC_SITE_COUNT",
]
