"""Encoding of a :class:`~usif.model.properties.PropertyMap` as self-describing columns.

Layout (little-endian)::

    u32 column_count
    column_count times, sorted by name (names unique):
        str  name            (u16 length + UTF-8)
        str  unit
        u8   dtype code      (see DTYPE_CODES; 0 = JSON)
        numeric: u8 ndim, u64 dims[ndim], raw C-order data
        JSON:    u64 length, canonical UTF-8 JSON text

Per-atom columns include the atom axis as their first dimension.

Decoding accepts only what encoding produces (sorted names, normalised unit
spelling, canonical JSON, the dtype the schema stores), so every value has
exactly one byte representation and ``encode(decode(b)) == b``.
"""

from __future__ import annotations

import json
from typing import Dict

import numpy as np

from usif.codec.wire import ByteReader, ByteWriter
from usif.errors import FormatError, ValidationError
from usif.model.properties import JSON, PropertyMap
from usif.units import normalize_unit

__all__ = ["DTYPE_CODES", "decode_columns", "encode_columns"]

DTYPE_CODES: Dict[str, int] = {
    JSON: 0,
    np.dtype("bool").str: 1,
    np.dtype("<i1").str: 2,
    np.dtype("<i2").str: 3,
    np.dtype("<i4").str: 4,
    np.dtype("<i8").str: 5,
    np.dtype("<u1").str: 6,
    np.dtype("<u2").str: 7,
    np.dtype("<u4").str: 8,
    np.dtype("<u8").str: 9,
    np.dtype("<f4").str: 10,
    np.dtype("<f8").str: 11,
}
_CODE_TO_DTYPE = {code: dtype for dtype, code in DTYPE_CODES.items()}

MAX_NDIM = 8
MAX_COLUMNS = 65535


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _wire_dtype(dtype: str) -> str:
    return dtype if dtype == JSON else np.dtype(dtype).newbyteorder("<").str


def _dtype_code(dtype: str) -> int:
    try:
        return DTYPE_CODES[_wire_dtype(dtype)]
    except KeyError:  # pragma: no cover - PropertyMap only stores whitelisted dtypes
        raise ValidationError(f"dtype {dtype} cannot be encoded") from None


def encode_columns(writer: ByteWriter, columns: PropertyMap) -> None:
    names = sorted(columns)
    if len(names) > MAX_COLUMNS:
        raise ValidationError(f"too many properties ({len(names)} > {MAX_COLUMNS})")
    writer.u32(len(names))
    for name in names:
        dtype = columns.dtype(name)
        writer.string(name)
        writer.string(columns.unit(name))
        writer.u8(_dtype_code(dtype))
        value = columns.raw(name)
        if dtype == JSON:
            text = canonical_json(value)
            writer.u64(len(text))
            writer.raw(text)
        else:
            array = np.asarray(value).astype(_wire_dtype(dtype), copy=False)
            writer.u8(array.ndim)
            for dim in array.shape:
                writer.u64(dim)
            writer.array(array)


def decode_columns(reader: ByteReader, target: PropertyMap) -> None:
    """Read columns into ``target``, validating them through the map's schema."""
    count = reader.u32("column count")
    if count > MAX_COLUMNS:
        raise FormatError(f"column count {count} exceeds {MAX_COLUMNS}")
    previous = None
    for _ in range(count):
        name = reader.string("column name")
        if previous is not None and name <= previous:
            raise FormatError(f"columns are not unique and sorted at {name!r}")
        previous = name
        unit = reader.string("column unit")
        if normalize_unit(unit) != unit:
            raise FormatError(f"column {name!r} unit {unit!r} is not in normalised spelling")
        code = reader.u8("column dtype")
        dtype = _CODE_TO_DTYPE.get(code)
        if dtype is None:
            raise FormatError(f"column {name!r} has unknown dtype code {code}")
        if dtype == JSON:
            size = reader.u64("JSON length")
            raw = reader.raw(size, f"JSON column {name!r}")
            try:
                value = json.loads(str(raw, "utf-8"))
                canonical = canonical_json(value) == raw
            except (UnicodeDecodeError, ValueError, RecursionError) as exc:
                raise FormatError(f"column {name!r} holds invalid JSON: {exc}") from exc
            if not canonical:
                raise FormatError(f"column {name!r} JSON is not in canonical form")
        else:
            ndim = reader.u8("column ndim")
            if ndim > MAX_NDIM:
                raise FormatError(f"column {name!r} has {ndim} dimensions (max {MAX_NDIM})")
            shape = tuple(reader.u64("column dimension") for _ in range(ndim))
            size = int(np.prod(shape, dtype=object)) if shape else 1
            itemsize = np.dtype(dtype).itemsize
            if size * itemsize > reader.remaining:
                raise FormatError(f"column {name!r} declares more data than the section holds")
            value = reader.array(np.dtype(dtype), size, f"column {name!r}").reshape(shape)
        try:
            target.set(name, value, unit=unit)
        except ValidationError as exc:
            raise FormatError(f"column {name!r} is invalid: {exc}") from exc
        if _wire_dtype(target.dtype(name)) != dtype:
            raise FormatError(
                f"column {name!r} is stored as {dtype} but the schema keeps it as "
                f"{target.dtype(name)}"
            )
