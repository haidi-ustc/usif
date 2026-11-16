"""Read-only reader for ``.usifc`` version-2 containers written by USIF 0.8 and earlier.

Frozen like :mod:`usif.upgrade.format6`. Layout reference::

    header (64 bytes): magic b"USIFC\\0\\0" | version u8 = 2 | count u32 |
                       data_offset u64 | index_offset u64 | 2 x u64 reserved |
                       compression u8 | chunking u8 | created u64 | updated u64 | 2 reserved
    records: format-5/6 records at chunk_id * 64 MiB + chunk_offset
    index block: b"USIFIDX2" | generation u64 | payload_size u64 | crc32 u32 |
                 4 reserved | payload | b"USIFDONE"

If the header does not point at a valid index block, the newest valid block
found by scanning the file is used (as 0.8 did).
"""

from __future__ import annotations

import json
import mmap
import os
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from usif.codec.wire import ByteReader
from usif.errors import ChecksumError, FormatError

__all__ = ["V2Container", "V2Entry", "is_container_v2", "open_container_v2"]

MAGIC = b"USIFC\x00\x00"
VERSION = 2
HEADER_SIZE = 64
CHUNK_SIZE = 64 * 1024 * 1024
INDEX_MAGIC = b"USIFIDX2"
INDEX_COMMIT = b"USIFDONE"
SECONDARY_MAGIC = b"SIDX0002"
_INDEX_HEADER = struct.Struct("<8sQQI4s")
MAX_RECORD_SIZE = 1024**3
MAX_GROUP_DEPTH = 256


@dataclass(frozen=True)
class V2Entry:
    """One (group, name) -> record reference; ``name`` is None for unnamed adds."""

    group: str
    name: Optional[str]
    record_hash: str
    attrs: Dict[str, Any] = field(default_factory=dict)


def is_container_v2(path: Union[str, os.PathLike[str]]) -> bool:
    try:
        with open(path, "rb") as handle:
            head = handle.read(8)
    except OSError:
        return False
    return head[:7] == MAGIC and head[7:8] == bytes([VERSION])


def _string_u16(reader: ByteReader, what: str) -> str:
    raw = bytes(reader.raw(reader.u16(f"{what} length"), what))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FormatError(f"{what} is not UTF-8") from exc


def _json_value(reader: ByteReader, what: str) -> Any:
    raw = bytes(reader.raw(reader.u32(f"{what} length"), what))
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise FormatError(f"{what} is not valid JSON") from exc


class V2Container:
    """A v2 container opened read-only (use as a context manager)."""

    def __init__(self, path: Union[str, os.PathLike[str]]) -> None:
        self.path = Path(path)
        self._file = open(self.path, "rb")
        try:
            size = os.fstat(self._file.fileno()).st_size
            if size < HEADER_SIZE:
                raise FormatError(f"{self.path} is too small to be a v2 container")
            self._map = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
            self._parse()
        except BaseException:
            self._file.close()
            raise

    # -- lifecycle ------------------------------------------------------------

    def close(self) -> None:
        if not self._file.closed:
            self._map.close()
            self._file.close()

    def __enter__(self) -> "V2Container":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- parsing ----------------------------------------------------------------

    def _parse(self) -> None:
        header = ByteReader(self._map[:HEADER_SIZE], "v2 container header")
        if bytes(header.raw(7, "magic")) != MAGIC:
            raise FormatError(f"{self.path} is not a USIF v2 container")
        version = header.u8("version")
        if version != VERSION:
            raise FormatError(f"container version {version} is not 2")
        self.record_count = header.u32("record count")
        header.u64("data offset")
        index_offset = header.u64("index offset")
        header.raw(16, "reserved offsets")
        self.compression = header.u8("compression")
        header.u8("chunking")
        self.created = header.u64("created")
        self.updated = header.u64("updated")

        payload = None
        self.recovered = False
        if index_offset:
            try:
                payload = self._index_block(index_offset)[1]
            except FormatError:
                payload = None
        if payload is None:
            payload = self._scan_for_index()
            self.recovered = True
        self._parse_index(payload)

    def _index_block(self, offset: int) -> Tuple[int, bytes]:
        end = offset + _INDEX_HEADER.size
        if offset < HEADER_SIZE or end > len(self._map):
            raise FormatError(f"index offset {offset} is outside the file")
        magic, generation, size, checksum, _ = _INDEX_HEADER.unpack(self._map[offset:end])
        if magic != INDEX_MAGIC:
            raise FormatError(f"no index block at offset {offset}")
        if end + size + len(INDEX_COMMIT) > len(self._map):
            raise FormatError("index block is truncated")
        payload = bytes(self._map[end : end + size])
        if self._map[end + size : end + size + len(INDEX_COMMIT)] != INDEX_COMMIT:
            raise FormatError("index block has no commit marker")
        if zlib.crc32(payload) & 0xFFFFFFFF != checksum:
            raise ChecksumError("index block checksum mismatch")
        return generation, payload

    def _scan_for_index(self) -> bytes:
        best: Optional[Tuple[int, bytes]] = None
        position = self._map.find(INDEX_MAGIC, HEADER_SIZE)
        while position >= 0:
            try:
                block = self._index_block(position)
                if best is None or block[0] > best[0]:
                    best = block
            except FormatError:
                pass
            position = self._map.find(INDEX_MAGIC, position + 1)
        if best is None:
            raise FormatError(f"{self.path} has no valid index block")
        return best[1]

    def _parse_index(self, payload: bytes) -> None:
        reader = ByteReader(payload, "v2 index")
        self.records: Dict[str, Tuple[int, int]] = {}
        for _ in range(reader.u32("record count")):
            record_hash = _string_u16(reader, "record hash")
            chunk = reader.u32("chunk id")
            offset = reader.u64("chunk offset")
            size = reader.u32("record size")
            start = chunk * CHUNK_SIZE + offset
            if size > MAX_RECORD_SIZE or start < HEADER_SIZE or start + size > len(self._map):
                raise FormatError(f"record {record_hash[:16]} lies outside the file")
            self.records[record_hash] = (start, size)
        names: Dict[str, str] = {}
        for _ in range(reader.u32("name count")):
            name = _string_u16(reader, "name")
            names[name] = _string_u16(reader, "named record hash")
        attrs: Dict[str, Dict[str, Any]] = {}
        for _ in range(reader.u32("attribute entry count")):
            name = _string_u16(reader, "attribute owner")
            attrs[name] = {
                _string_u16(reader, "attribute name"): _json_value(reader, "attribute value")
                for _ in range(reader.u16("attribute count"))
            }
        groups: Dict[str, Dict[str, Any]] = {}
        members: List[Tuple[str, str, str]] = []
        tree = reader.raw(reader.u32("group tree size"), "group tree")
        if len(tree):
            tree_reader = ByteReader(tree, "v2 group tree")
            self._parse_group(tree_reader, "", groups, members, depth=0)
            tree_reader.expect_end()
        if bytes(reader.raw(8, "secondary index magic")) != SECONDARY_MAGIC:
            raise FormatError("v2 index has no secondary index section")
        reader.raw(reader.u32("secondary index size"), "secondary index")
        reader.expect_end()

        for record_hash in list(names.values()) + [m[2] for m in members]:
            if record_hash not in self.records:
                raise FormatError(f"index references unknown record {record_hash[:16]}")
        self.group_attrs = groups
        self.entries = self._build_entries(names, attrs, members)

    def _parse_group(
        self,
        reader: ByteReader,
        parent: str,
        groups: Dict[str, Dict[str, Any]],
        members: List[Tuple[str, str, str]],
        depth: int,
    ) -> None:
        if depth > MAX_GROUP_DEPTH:
            raise FormatError("v2 group tree is too deep")
        name = _string_u16(reader, "group name")
        path = "/" if depth == 0 else f"{parent.rstrip('/')}/{name}"
        for _ in range(reader.u32("group member count")):
            member = _string_u16(reader, "group member")
            members.append((path, member, _string_u16(reader, "group member hash")))
        groups[path] = {
            _string_u16(reader, "group attribute name"): _json_value(reader, "group attribute")
            for _ in range(reader.u16("group attribute count"))
        }
        for _ in range(reader.u32("subgroup count")):
            self._parse_group(reader, path, groups, members, depth + 1)

    def _build_entries(
        self,
        names: Dict[str, str],
        attrs: Dict[str, Dict[str, Any]],
        members: List[Tuple[str, str, str]],
    ) -> List[V2Entry]:
        entries: List[V2Entry] = []
        placed: set[str] = set()
        referenced: set[str] = set()
        for group, member, record_hash in members:
            referenced.add(record_hash)
            if names.get(member) == record_hash:
                entries.append(V2Entry(group, member, record_hash, attrs.get(member, {})))
                placed.add(member)
            elif member == record_hash[:16]:
                entries.append(V2Entry(group, None, record_hash))
            # otherwise: a stale alias that was later re-pointed; 0.8 ignored it too
        for name, record_hash in names.items():
            if name not in placed:
                entries.append(V2Entry("/", name, record_hash, attrs.get(name, {})))
                referenced.add(record_hash)
        for record_hash in self.records:
            if record_hash not in referenced:
                entries.append(V2Entry("/", None, record_hash))
        return entries

    # -- access -----------------------------------------------------------------

    def record_bytes(self, record_hash: str) -> bytes:
        start, size = self.records[record_hash]
        return bytes(self._map[start : start + size])

    def __iter__(self) -> Iterator[V2Entry]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)


def open_container_v2(path: Union[str, os.PathLike[str]]) -> V2Container:
    return V2Container(path)
