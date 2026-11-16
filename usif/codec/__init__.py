"""Byte formats for a single structure: the ``.usif`` record and the JSON document."""

from usif.codec.record import (
    FORMAT_VERSION,
    RecordHeader,
    RecordInfo,
    decode,
    decode_with_info,
    encode,
    encode_with_info,
    is_record,
    read_header,
)

__all__ = [
    "FORMAT_VERSION",
    "RecordHeader",
    "RecordInfo",
    "decode",
    "decode_with_info",
    "encode",
    "encode_with_info",
    "is_record",
    "read_header",
]
