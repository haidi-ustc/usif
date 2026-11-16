"""The ``.usif`` record format, version 7.

Header (40 bytes, little-endian)::

    magic        8  b"\\x89USIF\\r\\n\\x1a"
    version      u16  7
    flags        u16  0 (reserved; non-zero is rejected)
    compression  u8   codec id (see usif.codec.compression)
    reserved     3    zero
    raw_size     u64  payload size after decompression
    stored_size  u64  payload size as stored
    digest       8    BLAKE2b-64 of the stored payload

Payload: a sequence of sections ``tag (4 ASCII) | size u64 | body``, in the
canonical order ATOM, CELL?, POSN|SYMM, ARRS?, PROP?. Tags starting with a
lower-case letter are ancillary and skipped by readers that do not know
them; any other unknown tag is an error.

Identity hashes are computed from bytes, so they need no decoding:

* ``record_hash``: BLAKE2b-256 of the raw payload;
* ``geometry_hash``: BLAKE2b-256 of the ATOM, CELL and POSN/SYMM sections.

Encoding is canonical (fixed section order, sorted columns, canonical JSON),
so equal structures encoded with equal options give identical bytes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np

from usif.codec import compression as _compression
from usif.codec.columns import decode_columns, encode_columns
from usif.codec.wire import ByteReader, ByteWriter
from usif.errors import ChecksumError, FormatError, UnsupportedVersionError, ValidationError
from usif.model.cell import Cell
from usif.model.properties import DEFAULT_SCHEMA, Schema
from usif.model.structure import Structure
from usif.version import FORMAT_VERSION

__all__ = [
    "FORMAT_VERSION",
    "HEADER_SIZE",
    "MAGIC",
    "RecordHeader",
    "RecordInfo",
    "decode",
    "decode_with_info",
    "encode",
    "encode_with_info",
    "is_record",
    "read_header",
]

MAGIC = b"\x89USIF\r\n\x1a"
HEADER_SIZE = 40
#: Default upper bound on the decompressed payload accepted by :func:`decode`.
DEFAULT_MAX_SIZE = 2 * 1024**3
#: Upper bound on atoms per record.
MAX_ATOMS = 100_000_000

Precision = Literal["f64", "f32"]
SymmetryMode = Literal["off", "auto"]

_TAG_ATOM, _TAG_CELL, _TAG_POSN, _TAG_SYMM = b"ATOM", b"CELL", b"POSN", b"SYMM"
_TAG_ARRS, _TAG_PROP = b"ARRS", b"PROP"
_GEOMETRY_TAGS = (_TAG_ATOM, _TAG_CELL, _TAG_POSN, _TAG_SYMM)
# Wire dtypes. Every array is cast to one of these before it is written, so the
# bytes never depend on the dtype an array happens to have in memory.
_U1, _U2, _U4, _F4, _F8 = (np.dtype(t) for t in ("<u1", "<u2", "<u4", "<f4", "<f8"))
_PRECISIONS: Dict[str, Tuple[int, np.dtype[Any]]] = {"f64": (11, _F8), "f32": (10, _F4)}
_POSITION_DTYPES: Dict[int, np.dtype[Any]] = {code: dtype for code, dtype in _PRECISIONS.values()}
_SYMM_IDENTITY_P, _SYMM_ZERO_P, _SYMM_ORDER = 0x01, 0x02, 0x04
_MAX_HALL = 530
_U16_MAX = 0xFFFF


@dataclass(frozen=True)
class RecordHeader:
    version: int
    compression: int
    raw_size: int
    stored_size: int
    digest: bytes

    @property
    def record_size(self) -> int:
        return HEADER_SIZE + self.stored_size


@dataclass(frozen=True)
class RecordInfo:
    """Identity and size of an encoded record."""

    record_hash: str
    geometry_hash: str
    natoms: int
    compression: str
    raw_size: int
    stored_size: int
    symmetric: bool


# -- header ---------------------------------------------------------------------


def is_record(data: bytes | memoryview) -> bool:
    return bytes(data[: len(MAGIC)]) == MAGIC


def read_header(data: bytes | memoryview) -> RecordHeader:
    reader = ByteReader(memoryview(data)[:HEADER_SIZE], "record header")
    if bytes(reader.raw(8, "magic")) != MAGIC:
        raise FormatError("not a USIF format-7 record (bad magic)")
    version = reader.u16("version")
    if version != FORMAT_VERSION:
        raise UnsupportedVersionError(f"record version {version} is not {FORMAT_VERSION}")
    flags = reader.u16("flags")
    if flags:
        raise UnsupportedVersionError(f"record uses unknown header flags {flags:#06x}")
    compression = reader.u8("compression")
    if bytes(reader.raw(3, "reserved")) != b"\x00\x00\x00":
        raise FormatError("reserved header bytes are not zero")
    raw_size = reader.u64("raw size")
    stored_size = reader.u64("stored size")
    digest = bytes(reader.raw(8, "digest"))
    return RecordHeader(version, compression, raw_size, stored_size, digest)


def _digest(data: bytes | memoryview) -> bytes:
    return hashlib.blake2b(data, digest_size=8).digest()


def _hash(*parts: bytes | memoryview) -> str:
    h = hashlib.blake2b(digest_size=32)
    for part in parts:
        h.update(part)
    return h.hexdigest()


# -- encoding -------------------------------------------------------------------


def _section(out: ByteWriter, tag: bytes, body: bytes) -> None:
    out.raw(tag)
    out.u64(len(body))
    out.raw(body)


def _exact(array: np.ndarray, dtype: np.dtype[Any], what: str) -> np.ndarray:
    """``array`` as ``dtype``, refusing any cast that changes a value."""
    cast = np.asarray(array).astype(dtype)
    if not np.array_equal(cast, array):
        raise ValidationError(f"{what} do not fit the record type {dtype}")
    return cast


def _atom_body(structure: Structure) -> bytes:
    w = ByteWriter()
    w.u32(structure.natoms)
    w.array(_exact(structure.numbers, _U1, "atomic numbers"))
    return w.getvalue()


def _cell_body(cell: Cell) -> bytes:
    w = ByteWriter()
    w.u8(sum(1 << i for i, flag in enumerate(cell.pbc) if flag))
    w.array(_exact(cell.matrix, _F8, "cell vectors"))
    return w.getvalue()


def _posn_body(structure: Structure, precision: Precision) -> bytes:
    if precision not in _PRECISIONS:
        raise ValidationError(f"precision must be 'f64' or 'f32', got {precision!r}")
    code, dtype = _PRECISIONS[precision]
    with np.errstate(over="ignore"):
        positions = structure.positions.astype(dtype)  # f32 rounds by design
    if not np.all(np.isfinite(positions)):
        raise ValidationError(f"positions overflow {precision}")
    w = ByteWriter()
    w.u8(code)
    w.array(positions)
    return w.getvalue()


def _symm_body(structure: Structure) -> Optional[bytes]:
    from usif.symmetry import reduce

    form = reduce(structure)
    if form is None:
        return None
    identity_P = np.array_equal(form.transformation, np.eye(3))
    zero_p = not np.any(form.origin_shift)
    flags = (
        (_SYMM_IDENTITY_P if identity_P else 0)
        | (_SYMM_ZERO_P if zero_p else 0)
        | (_SYMM_ORDER if form.order is not None else 0)
    )
    if not 1 <= form.hall_number <= _MAX_HALL:  # pragma: no cover - spglib guarantees this
        raise ValidationError(f"Hall number {form.hall_number} out of range")
    w = ByteWriter()
    w.u16(form.hall_number)
    w.u8(flags)
    if not identity_P:
        w.array(_exact(form.transformation, _F8, "setting transformation"))
    if not zero_p:
        w.array(_exact(form.origin_shift, _F8, "origin shift"))
    w.u32(len(form.numbers))
    w.array(_exact(form.numbers, _U1, "representative atomic numbers"))
    w.array(_exact(form.multiplicities, _U4, "multiplicities"))
    w.array(_exact(form.positions, _F8, "representative positions"))
    if form.order is not None:
        wide = structure.natoms > _U16_MAX + 1
        w.u8(4 if wide else 2)
        w.array(_exact(form.order, _U4 if wide else _U2, "atom order"))
    return w.getvalue()


def _check_options(structure: Structure, symmetry: SymmetryMode) -> None:
    if symmetry not in ("off", "auto"):
        raise ValidationError(f"symmetry must be 'off' or 'auto', got {symmetry!r}")
    if structure.natoms > MAX_ATOMS:
        raise ValidationError(f"structure has more than {MAX_ATOMS} atoms")


def _payload(structure: Structure, geometry_tag: bytes, geometry: bytes) -> Tuple[bytes, int]:
    """Return (payload, end offset of the geometry sections)."""
    out = ByteWriter()
    _section(out, _TAG_ATOM, _atom_body(structure))
    if structure.cell is not None:
        _section(out, _TAG_CELL, _cell_body(structure.cell))
    _section(out, geometry_tag, geometry)
    geometry_end = len(out)
    if len(structure.arrays):
        w = ByteWriter()
        encode_columns(w, structure.arrays)
        _section(out, _TAG_ARRS, w.getvalue())
    if len(structure.properties):
        w = ByteWriter()
        encode_columns(w, structure.properties)
        _section(out, _TAG_PROP, w.getvalue())
    return out.getvalue(), geometry_end


def encode_with_info(
    structure: Structure,
    *,
    compression: str = "zlib",
    level: Optional[int] = None,
    precision: Precision = "f64",
    symmetry: SymmetryMode = "off",
) -> Tuple[bytes, RecordInfo]:
    """Encode ``structure`` and return ``(record_bytes, info)``.

    * ``precision``: ``"f64"`` (exact) or ``"f32"`` (compact) positions.
    * ``symmetry``: ``"auto"`` stores the asymmetric unit when that is
      lossless (within 1e-5 Å, original atom order kept) and makes the
      stored record smaller.
    * ``compression``: a registered codec name (``none``, ``zlib``, ``lzma``,
      ``zstd``).
    """
    if not isinstance(structure, Structure):
        raise ValidationError(f"expected a Structure, got {type(structure).__name__}")
    codec = _compression.get(compression)
    _check_options(structure, symmetry)
    candidates = [(_TAG_POSN, _posn_body(structure, precision))]
    if symmetry == "auto":
        symm = _symm_body(structure)
        if symm is not None:
            candidates.append((_TAG_SYMM, symm))
    # Keep the asymmetric unit only when it makes the stored record smaller.
    best: Optional[Tuple[bytes, bytes, int, bool]] = None
    for tag, body in candidates:
        payload, geometry_end = _payload(structure, tag, body)
        stored = codec.compress(payload, level)
        if best is None or len(stored) < len(best[1]):
            best = (payload, stored, geometry_end, tag == _TAG_SYMM)
    assert best is not None  # nosec B101
    payload, stored, geometry_end, symmetric = best
    header = ByteWriter()
    header.raw(MAGIC)
    header.u16(FORMAT_VERSION)
    header.u16(0)
    header.u8(codec.id)
    header.raw(b"\x00\x00\x00")
    header.u64(len(payload))
    header.u64(len(stored))
    header.raw(_digest(stored))
    info = RecordInfo(
        record_hash=_hash(payload),
        geometry_hash=_hash(memoryview(payload)[:geometry_end]),
        natoms=structure.natoms,
        compression=codec.name,
        raw_size=len(payload),
        stored_size=len(stored),
        symmetric=symmetric,
    )
    return header.getvalue() + stored, info


def encode(
    structure: Structure,
    *,
    compression: str = "zlib",
    level: Optional[int] = None,
    precision: Precision = "f64",
    symmetry: SymmetryMode = "off",
) -> bytes:
    """Encode ``structure`` as a format-7 record (see :func:`encode_with_info`)."""
    return encode_with_info(
        structure, compression=compression, level=level, precision=precision, symmetry=symmetry
    )[0]


# -- decoding -------------------------------------------------------------------


def _open_payload(data: bytes | memoryview, max_size: int) -> Tuple[RecordHeader, bytes]:
    view = memoryview(data)
    header = read_header(view)
    if header.raw_size > max_size:
        raise FormatError(f"record payload of {header.raw_size} bytes exceeds limit {max_size}")
    if len(view) < header.record_size:
        raise FormatError(
            f"record truncated: {len(view)} bytes, header declares {header.record_size}"
        )
    if len(view) > header.record_size:
        raise FormatError(f"{len(view) - header.record_size} trailing bytes after record")
    stored = view[HEADER_SIZE : header.record_size]
    if _digest(stored) != header.digest:
        raise ChecksumError("record payload digest mismatch (corrupted data)")
    codec = _compression.get(header.compression)
    return header, codec.decompress(bytes(stored), header.raw_size)


def _split_sections(payload: bytes) -> Tuple[Dict[bytes, memoryview], int]:
    reader = ByteReader(payload, "record payload")
    sections: Dict[bytes, memoryview] = {}
    order: List[bytes] = []
    geometry_end = 0
    while reader.remaining:
        tag = bytes(reader.raw(4, "section tag"))
        size = reader.u64("section size")
        body = reader.raw(size, f"section {tag!r}")
        if not tag[:1].islower():
            if tag not in (*_GEOMETRY_TAGS, _TAG_ARRS, _TAG_PROP):
                raise FormatError(f"unknown critical section {tag!r}")
            if tag in sections:
                raise FormatError(f"duplicate section {tag!r}")
            sections[tag] = body
            order.append(tag)
            if tag in _GEOMETRY_TAGS:
                geometry_end = reader.position
    canonical = (_TAG_ATOM, _TAG_CELL, _TAG_POSN, _TAG_SYMM, _TAG_ARRS, _TAG_PROP)
    if order != [t for t in canonical if t in sections]:
        raise FormatError(f"sections out of canonical order: {order}")
    if _TAG_ATOM not in sections:
        raise FormatError("record has no ATOM section")
    if (_TAG_POSN in sections) == (_TAG_SYMM in sections):
        raise FormatError("record needs exactly one of POSN and SYMM")
    return sections, geometry_end


def _read_numbers(body: memoryview) -> np.ndarray:
    reader = ByteReader(body, "ATOM section")
    count = reader.u32("atom count")
    if not 0 < count <= MAX_ATOMS:
        raise FormatError(f"atom count {count} out of range")
    numbers = reader.array(_U1, count, "atomic numbers")
    reader.expect_end()
    return numbers


def _read_cell(body: memoryview) -> Cell:
    reader = ByteReader(body, "CELL section")
    mask = reader.u8("pbc mask")
    if mask > 7:
        raise FormatError(f"invalid pbc mask {mask}")
    matrix = reader.array(_F8, 9, "cell matrix").reshape(3, 3)
    reader.expect_end()
    try:
        return Cell(matrix, tuple(bool(mask & (1 << i)) for i in range(3)))
    except ValidationError as exc:
        raise FormatError(f"CELL section holds an invalid cell: {exc}") from exc


def _read_positions(body: memoryview, count: int) -> np.ndarray:
    reader = ByteReader(body, "POSN section")
    code = reader.u8("position dtype")
    dtype = _POSITION_DTYPES.get(code)
    if dtype is None:
        raise FormatError(f"invalid position dtype code {code}")
    positions = reader.array(dtype, count * 3, "positions").reshape(count, 3)
    reader.expect_end()
    return positions


def _read_symmetric(body: memoryview, numbers: np.ndarray, cell: Optional[Cell]) -> np.ndarray:
    from usif.symmetry.expand import SymmetricForm, expand

    if cell is None:
        raise FormatError("SYMM section needs a CELL section")
    reader = ByteReader(body, "SYMM section")
    hall = reader.u16("Hall number")
    flags = reader.u8("SYMM flags")
    if flags & ~(_SYMM_IDENTITY_P | _SYMM_ZERO_P | _SYMM_ORDER):
        raise FormatError(f"unknown SYMM flags {flags:#x}")
    P = (
        np.eye(3)
        if flags & _SYMM_IDENTITY_P
        else reader.array(_F8, 9, "transformation").reshape(3, 3)
    )
    p = np.zeros(3) if flags & _SYMM_ZERO_P else reader.array(_F8, 3, "origin shift")
    count = reader.u32("representative count")
    if not 0 < count <= len(numbers):
        raise FormatError(f"representative count {count} out of range")
    rep_numbers = reader.array(_U1, count, "representative numbers")
    multiplicities = reader.array(_U4, count, "multiplicities")
    rep_positions = reader.array(_F8, count * 3, "representatives").reshape(count, 3)
    order = None
    if flags & _SYMM_ORDER:
        width = reader.u8("order width")
        if width not in (2, 4):
            raise FormatError(f"invalid order width {width}")
        if width == 4 and len(numbers) <= _U16_MAX + 1:
            raise FormatError("atom order uses 4-byte indices where 2 bytes suffice")
        order = reader.array(_U2 if width == 2 else _U4, len(numbers), "atom order")
    reader.expect_end()
    if int(multiplicities.astype(np.int64).sum()) != len(numbers):
        raise FormatError("multiplicities do not add up to the atom count")
    try:
        form = SymmetricForm(hall, P, p, rep_numbers, multiplicities, rep_positions, order)
        expanded_numbers, frac = expand(form)
    except ValidationError as exc:
        raise FormatError(f"invalid SYMM section: {exc}") from exc
    if not np.array_equal(expanded_numbers, numbers):
        raise FormatError("SYMM expansion does not match the ATOM section")
    return cell.to_cartesian(frac)


def decode_with_info(
    data: bytes | memoryview,
    *,
    schema: Schema = DEFAULT_SCHEMA,
    max_size: int = DEFAULT_MAX_SIZE,
) -> Tuple[Structure, RecordInfo]:
    """Decode a format-7 record, verifying digest, sizes and structure."""
    header, payload = _open_payload(data, max_size)
    sections, geometry_end = _split_sections(payload)
    numbers = _read_numbers(sections[_TAG_ATOM])
    cell = _read_cell(sections[_TAG_CELL]) if _TAG_CELL in sections else None
    symmetric = _TAG_SYMM in sections
    if symmetric:
        positions = _read_symmetric(sections[_TAG_SYMM], numbers, cell)
    else:
        positions = _read_positions(sections[_TAG_POSN], len(numbers))
    try:
        structure = Structure(numbers, positions, cell, schema=schema)
    except ValidationError as exc:
        raise FormatError(f"record holds an invalid structure: {exc}") from exc
    if _TAG_ARRS in sections:
        reader = ByteReader(sections[_TAG_ARRS], "ARRS section")
        decode_columns(reader, structure.arrays)
        reader.expect_end()
    if _TAG_PROP in sections:
        reader = ByteReader(sections[_TAG_PROP], "PROP section")
        decode_columns(reader, structure.properties)
        reader.expect_end()
    info = RecordInfo(
        record_hash=_hash(payload),
        geometry_hash=_hash(memoryview(payload)[:geometry_end]),
        natoms=structure.natoms,
        compression=_compression.get(header.compression).name,
        raw_size=header.raw_size,
        stored_size=header.stored_size,
        symmetric=symmetric,
    )
    return structure, info


def decode(
    data: bytes | memoryview,
    *,
    schema: Schema = DEFAULT_SCHEMA,
    max_size: int = DEFAULT_MAX_SIZE,
) -> Structure:
    """Decode a format-7 record (see :func:`decode_with_info`)."""
    return decode_with_info(data, schema=schema, max_size=max_size)[0]
