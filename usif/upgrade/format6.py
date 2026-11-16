"""Read-only decoder for ``.usif`` records written by USIF 0.8 and earlier (formats 5 and 6).

This module is frozen: it reproduces how USIF 0.8 interpreted these records
and must not change when the current format evolves. Layout reference::

    header (64 bytes): magic b"USIF\\0\\0\\0" | version u8 (5 or 6) | raw_size u32 |
                       stored_size u32 | compression u8 (0 none, 1 gzip) |
                       geometry_hash 32 (SHA-256) | reserved 15
    payload: structure_type u8 (0 crystal, 1 molecule) | storage_mode u8
             (0 symmetric, 1 full) | body | u32-prefixed structure property
             section | u16-prefixed formula

The stored SHA-256 geometry hash is recomputed from the parsed fields and
checked, so corrupted geometry is detected even in uncompressed records.
"""

from __future__ import annotations

import hashlib
import json
import struct
import warnings
import zlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from usif.codec.wire import ByteReader
from usif.errors import ChecksumError, FormatError, UnsupportedVersionError, ValidationError
from usif.model.cell import Cell
from usif.model.properties import DEFAULT_SCHEMA, Schema
from usif.model.structure import Structure
from usif.symmetry.expand import canonical_order
from usif.symmetry.spacegroup import expand_orbit, setting_operations
from usif.symmetry.tables import FORMAT5_POINT_GROUP_ROTATIONS, FORMAT5_SPACEGROUP_HALL

__all__ = ["HEADER_SIZE", "MAGIC", "Format6Info", "decode", "decode_with_info", "is_format6"]

MAGIC = b"USIF\x00\x00\x00"
HEADER_SIZE = 64
VERSIONS = (5, 6)
MAX_PAYLOAD = 512 * 1024**2
MAX_ATOMS = 10_000_000
MAX_PROPERTY_BYTES = 64 * 1024**2
_CRYSTAL, _MOLECULE = 0, 1
_SYMMETRIC, _FULL = 0, 1
_IDENTITY_P, _ZERO_P = 0x01, 0x02
_CUSTOM_JSON_PREFIX = "__USIF_JSON__:"
_UNITS_KEY = "__usif_property_units__"
#: Internal reconstruction bookkeeping of 0.7/0.8, not user data; dropped.
_SYMMETRY_METADATA_KEY = "__usif_symmetry_metadata__"
#: Cartesian tolerance (Å) used by 0.8 to merge images of a molecular site.
_MOLECULE_MERGE = 1e-6

#: The 0.8 built-in property definitions: name -> (element count, per atom).
#: All built-in values were float64; ``0`` means a scalar.
_BUILTINS: Dict[str, Tuple[int, bool]] = {
    "force": (3, True),
    "charge": (0, True),
    "magmom": (0, True),
    "velocity": (3, True),
    "energy": (0, False),
    "stress": (6, False),
    "volume": (0, False),
    "pressure": (0, False),
    "temperature": (0, False),
}
_DEFAULT_UNITS = {
    "force": "eV/Å",
    "charge": "e",
    "magmom": "μB",
    "velocity": "Å/fs",
    "energy": "eV",
    "stress": "GPa",
    "volume": "Å^3",
    "pressure": "GPa",
    "temperature": "K",
}


@dataclass(frozen=True)
class Format6Info:
    version: int
    geometry_hash: str
    symmetric: bool


def is_format6(data: bytes | memoryview) -> bool:
    head = bytes(data[:8])
    return len(head) == 8 and head[:7] == MAGIC and head[7] in VERSIONS


# -- properties -----------------------------------------------------------------


@dataclass
class _Props:
    values: Dict[str, Any]
    units: Dict[str, str]


def _string_u8(reader: ByteReader, what: str) -> str:
    raw = bytes(reader.raw(reader.u8(f"{what} length"), what))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FormatError(f"{what} is not UTF-8") from exc


def _builtin_value(name: str, data: bytes) -> Any:
    count, per_atom = _BUILTINS[name]
    reader = ByteReader(data, f"property {name!r}")
    if per_atom:
        flag = reader.u8("atom value count")
        if flag == 255:
            flag = reader.u32("atom value count")
        if flag not in (0, 1):
            raise FormatError(f"per-atom property {name!r} holds {flag} values for one atom")
    width = max(count, 1)
    values = reader.array(np.dtype("<f8"), width, f"property {name!r}")
    reader.expect_end()
    return float(values[0]) if count == 0 else values.astype(np.float64)


def _custom_value(text: str) -> Any:
    if not text.startswith(_CUSTOM_JSON_PREFIX):
        return text
    try:
        return json.loads(text[len(_CUSTOM_JSON_PREFIX) :])
    except (ValueError, RecursionError):
        return text  # 0.8 kept undecodable payloads as plain strings


def _read_properties(reader: ByteReader, per_atom: bool) -> _Props:
    props = _Props({}, {})
    for _ in range(reader.u8("known property count")):
        name = _string_u8(reader, "property name")
        size = reader.u32("property size")
        if size > MAX_PROPERTY_BYTES:
            raise FormatError(f"property {name!r} of {size} bytes exceeds limit")
        data = bytes(reader.raw(size, f"property {name!r}"))
        if name not in _BUILTINS or _BUILTINS[name][1] != per_atom:
            warnings.warn(
                f"skipping property {name!r}: it was defined by a custom 0.8 registry",
                stacklevel=4,
            )
            continue
        props.values[name] = _builtin_value(name, data)
    for _ in range(reader.u8("custom property count")):
        name = _string_u8(reader, "custom property name")
        size = reader.u32("custom property size")
        if size > MAX_PROPERTY_BYTES:
            raise FormatError(f"custom property {name!r} of {size} bytes exceeds limit")
        try:
            text = bytes(reader.raw(size, f"custom property {name!r}")).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FormatError(f"custom property {name!r} is not UTF-8") from exc
        value = _custom_value(text)
        if name == _UNITS_KEY and isinstance(value, dict):
            props.units.update({str(k): str(v) for k, v in value.items()})
        elif name != _SYMMETRY_METADATA_KEY:
            props.values[name] = value
    return props


def _unit_for(name: str, units: Dict[str, str]) -> Optional[str]:
    return units.get(name) or _DEFAULT_UNITS.get(name)


def _apply_structure_props(structure: Structure, props: _Props) -> None:
    for name, value in props.values.items():
        if value is None:
            continue
        unit = _unit_for(name, props.units)
        structure.properties.set(name, value, unit=unit or "")


def _apply_atom_props(structure: Structure, per_atom: List[_Props]) -> None:
    names: Dict[str, None] = {}
    units: Dict[str, str] = {}
    for props in per_atom:
        names.update(dict.fromkeys(props.values))
        for key, unit in props.units.items():
            units.setdefault(key, unit)
    for name in names:
        values = [props.values.get(name) for props in per_atom]
        unit = _unit_for(name, units) or ""
        if name in _BUILTINS:
            present = np.array([v is not None for v in values])
            width = max(_BUILTINS[name][0], 1)
            filled = [np.zeros(width) if v is None else np.atleast_1d(v) for v in values]
            column = np.stack(filled) if width > 1 else np.concatenate(filled)
            structure.arrays.set(name, column, unit=unit)
            if not present.all():
                warnings.warn(
                    f"per-atom {name!r} is missing on {int((~present).sum())} atoms: stored "
                    f"as 0 there, with the mask {name + '_present'!r}",
                    stacklevel=4,
                )
                structure.arrays[f"{name}_present"] = present
        else:
            items = [v.tolist() if isinstance(v, np.ndarray) else v for v in values]
            structure.arrays.set(name, items, unit=unit)


# -- geometry ---------------------------------------------------------------------


@dataclass
class _Site:
    z: int
    multiplicity: int
    coords: np.ndarray
    occupancy: float


def _pack_count(out: bytearray, value: int, fmt: str, limit: int) -> None:
    if value < limit:
        out += struct.pack(fmt, value)
    else:
        out += struct.pack(fmt, limit) + struct.pack("<I", value)


def _fit(images: np.ndarray, multiplicity: int, label: str) -> np.ndarray:
    if len(images) != multiplicity:
        warnings.warn(
            f"{label} generates {len(images)} images but the record declares "
            f"multiplicity {multiplicity}; it was not stored losslessly",
            stacklevel=5,
        )
    return images[:multiplicity]


def _expand_crystal(
    sites: List[_Site], hall: int, P: np.ndarray, p: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    rotations, translations = setting_operations(hall, P, p)
    numbers, frac, occupancy = [], [], []
    for site in sites:
        images = expand_orbit(site.coords, rotations, translations, site.multiplicity)
        images = _fit(images, site.multiplicity, f"Wyckoff site Z={site.z}")
        numbers += [site.z] * len(images)
        frac.append(images)
        occupancy += [site.occupancy] * len(images)
    all_numbers = np.asarray(numbers, dtype=np.uint8)
    all_frac = np.concatenate(frac) if frac else np.zeros((0, 3))
    order = canonical_order(all_numbers, all_frac)
    return all_numbers[order], all_frac[order], np.asarray(occupancy)[order]


def _expand_molecule(
    sites: List[_Site], point_group: str
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    rotations = FORMAT5_POINT_GROUP_ROTATIONS.get(point_group or "C1")
    if rotations is None:
        warnings.warn(
            f"point group {point_group!r} has no stored operations; "
            "representative sites are repeated",
            stacklevel=4,
        )
    rows: List[Tuple[int, Tuple[float, float, float], float]] = []
    for site in sites:
        if rotations is None:
            images = np.repeat(site.coords[None, :], site.multiplicity, axis=0)
        else:
            found: List[np.ndarray] = []
            for rotation in rotations:
                image = np.asarray(rotation, dtype=float) @ site.coords
                if not any(np.linalg.norm(image - u) < _MOLECULE_MERGE for u in found):
                    found.append(image)
            images = _fit(np.array(found), site.multiplicity, f"point-group site Z={site.z}")
        rows += [
            (site.z, (float(image[0]), float(image[1]), float(image[2])), site.occupancy)
            for image in images
        ]
    rows.sort(key=lambda r: (r[0], tuple(round(c, 8) for c in r[1])))
    return (
        np.asarray([r[0] for r in rows], dtype=np.uint8),
        np.asarray([r[1] for r in rows], dtype=float).reshape(-1, 3),
        np.asarray([r[2] for r in rows], dtype=float),
    )


def _read_symmetric_sites(reader: ByteReader, version: int, out: bytearray) -> List[_Site]:
    count = reader.u8("site count") if version == 5 else reader.u32("site count")
    if count > MAX_ATOMS:
        raise FormatError(f"site count {count} exceeds limit")
    _pack_count(out, count, "<B", 0xFF)
    sites = []
    for _ in range(count):
        z = reader.u8("site atomic number")
        mult = reader.u16("multiplicity") if version == 5 else reader.u32("multiplicity")
        if not 0 < mult <= MAX_ATOMS:
            raise FormatError(f"multiplicity {mult} out of range")
        raw = bytes(reader.raw(16, "site coordinates and occupancy"))
        x, y, zc, occ = struct.unpack("<4f", raw)
        out += struct.pack("<B", z)
        _pack_count(out, mult, "<H", 0xFFFF)
        out += raw
        sites.append(_Site(z, mult, np.array([x, y, zc], dtype=float), float(occ)))
    return sites


def _read_full_atoms(
    reader: ByteReader, out: bytearray
) -> Tuple[np.ndarray, np.ndarray, List[_Props]]:
    count = reader.u32("atom count")
    if count > MAX_ATOMS:
        raise FormatError(f"atom count {count} exceeds limit")
    out += struct.pack("<I", count)
    numbers = np.empty(count, dtype=np.uint8)
    coords = np.empty((count, 3), dtype=np.float32)
    props = []
    for i in range(count):
        numbers[i] = reader.u8("atomic number")
        raw = bytes(reader.raw(12, "atom coordinates"))
        out += bytes([int(numbers[i])]) + raw
        coords[i] = np.frombuffer(raw, dtype="<f4")
        props.append(_read_properties(reader, per_atom=True))
    return numbers, coords.astype(np.float64), props


# -- record ---------------------------------------------------------------------------


def _decompress(stored: bytes, compression: int, raw_size: int) -> bytes:
    if compression == 0:
        payload = stored
    elif compression == 1:
        engine = zlib.decompressobj(wbits=31)
        try:
            payload = engine.decompress(stored, raw_size + 1)
        except zlib.error as exc:
            raise ChecksumError(f"corrupted gzip payload: {exc}") from exc
        if not engine.eof or engine.unconsumed_tail or engine.unused_data:
            raise FormatError("gzip payload is truncated or has trailing data")
    else:
        raise FormatError(f"unknown format-5/6 compression type {compression}")
    if len(payload) != raw_size:
        raise FormatError(f"payload is {len(payload)} bytes, header declares {raw_size}")
    return payload


def decode_with_info(
    data: bytes | memoryview, *, schema: Schema = DEFAULT_SCHEMA
) -> Tuple[Structure, Format6Info]:
    """Decode a format-5/6 record into a :class:`Structure`.

    Symmetric records are expanded exactly as USIF 0.8 did (atoms ordered by
    atomic number, then coordinates); site occupancies other than 1 become a
    per-atom ``occupancy`` array.
    """
    view = memoryview(data)
    if len(view) < HEADER_SIZE:
        raise FormatError("record shorter than the 64-byte format-5/6 header")
    header = ByteReader(view[:HEADER_SIZE], "format-5/6 header")
    if bytes(header.raw(7, "magic")) != MAGIC:
        raise FormatError("not a format-5/6 USIF record")
    version = header.u8("version")
    if version not in VERSIONS:
        raise UnsupportedVersionError(f"record version {version} is not 5 or 6")
    raw_size = header.u32("raw size")
    stored_size = header.u32("stored size")
    compression = header.u8("compression")
    geometry_hash = bytes(header.raw(32, "geometry hash"))
    if raw_size > MAX_PAYLOAD or stored_size > MAX_PAYLOAD:
        raise FormatError("payload exceeds the format-5/6 size limit")
    if len(view) != HEADER_SIZE + stored_size:
        raise FormatError(
            f"record is {len(view)} bytes, header declares {HEADER_SIZE + stored_size}"
        )
    payload = _decompress(bytes(view[HEADER_SIZE:]), compression, raw_size)

    reader = ByteReader(payload, "format-5/6 payload")
    stype = reader.u8("structure type")
    smode = reader.u8("storage mode")
    if stype not in (_CRYSTAL, _MOLECULE) or smode not in (_SYMMETRIC, _FULL):
        raise FormatError(f"invalid structure type/storage mode {stype}/{smode}")
    hashed = bytearray([stype, smode])
    cell: Optional[Cell] = None
    occupancy: Optional[np.ndarray] = None
    atom_props: List[_Props] = []
    try:
        if stype == _CRYSTAL:
            lattice_raw = bytes(reader.raw(36, "lattice"))
            lattice = np.frombuffer(lattice_raw, dtype="<f4").astype(np.float64).reshape(3, 3)
            spacegroup = reader.u16("space group")
            hashed += lattice_raw + struct.pack("<H", spacegroup)
            cell = Cell(lattice)
            if smode == _SYMMETRIC:
                if version == 5:
                    if spacegroup not in FORMAT5_SPACEGROUP_HALL:
                        raise FormatError(f"invalid space group {spacegroup}")
                    hall, P, p = FORMAT5_SPACEGROUP_HALL[spacegroup], np.eye(3), np.zeros(3)
                else:
                    hall = reader.u16("Hall number")
                    flags = reader.u8("setting flags")
                    if flags & ~(_IDENTITY_P | _ZERO_P):
                        raise FormatError(f"unknown setting flags {flags:#x}")
                    P = (
                        np.eye(3)
                        if flags & _IDENTITY_P
                        else reader.array(np.dtype("<f8"), 9, "transformation").reshape(3, 3)
                    )
                    p = (
                        np.zeros(3)
                        if flags & _ZERO_P
                        else reader.array(np.dtype("<f8"), 3, "origin shift").copy()
                    )
                default = (
                    hall == FORMAT5_SPACEGROUP_HALL.get(spacegroup)
                    and np.array_equal(P, np.eye(3))
                    and not np.any(p)
                )
                if not default:
                    hashed += b"SETTING" + struct.pack("<H", hall)
                    hashed += struct.pack("<9d", *P.ravel()) + struct.pack("<3d", *p)
                sites = _read_symmetric_sites(reader, version, hashed)
                numbers, frac, occupancy = _expand_crystal(sites, hall, P, p)
                positions = cell.to_cartesian(frac)
            else:
                numbers, frac, atom_props = _read_full_atoms(reader, hashed)
                positions = cell.to_cartesian(frac)
        else:
            if smode == _SYMMETRIC:
                point_group = _string_u8(reader, "point group")
                pg = (point_group or "C1").encode("utf-8")
                hashed += struct.pack("<B", len(pg)) + pg
                sites = _read_symmetric_sites(reader, version, hashed)
                numbers, positions, occupancy = _expand_molecule(sites, point_group)
            else:
                numbers, positions, atom_props = _read_full_atoms(reader, hashed)
        section = ByteReader(
            reader.raw(reader.u32("structure property size"), "structure properties"),
            "structure properties",
        )
        structure_props = _read_properties(section, per_atom=False)
        section.expect_end()
        reader.raw(reader.u16("formula length"), "formula")
        reader.expect_end()
    except (ValidationError, KeyError, ValueError) as exc:
        if isinstance(exc, FormatError):
            raise
        raise FormatError(f"invalid format-{version} record: {exc}") from exc

    if hashlib.sha256(bytes(hashed)).digest() != geometry_hash:
        raise ChecksumError("format-5/6 geometry hash mismatch (corrupted record)")
    try:
        structure = Structure(numbers, positions, cell, schema=schema)
        if atom_props:
            _apply_atom_props(structure, atom_props)
        if occupancy is not None and np.any(occupancy != 1.0):
            structure.arrays["occupancy"] = occupancy
        _apply_structure_props(structure, structure_props)
    except ValidationError as exc:
        raise FormatError(f"format-{version} record holds invalid data: {exc}") from exc
    info = Format6Info(version, geometry_hash.hex(), smode == _SYMMETRIC)
    return structure, info


def decode(data: bytes | memoryview, *, schema: Schema = DEFAULT_SCHEMA) -> Structure:
    """Decode a format-5/6 record (see :func:`decode_with_info`)."""
    return decode_with_info(data, schema=schema)[0]
