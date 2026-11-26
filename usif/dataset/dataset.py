"""``.usifc`` datasets: many structures, deduplicated, grouped, annotated and queryable."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple, Union

from usif.codec.record import RecordInfo, decode, decode_with_info, encode_with_info
from usif.dataset.query import Q, normalize_group
from usif.dataset.sql import SCHEMA_VERSION, Mode, connect
from usif.elements import atomic_number
from usif.errors import DatasetError, FormatError, ValidationError
from usif.fileio import fsync_directory
from usif.model.properties import DEFAULT_SCHEMA, JSON, Schema, normalize_json
from usif.model.structure import Structure

__all__ = ["CheckReport", "Dataset", "Entry"]

PAGE_SIZE = 1000
MAX_NAME_BYTES = 255
MAX_ATTRS_BYTES = 1024 * 1024
_FROM = "FROM entries e JOIN records r ON r.id = e.record_id"


@dataclass(frozen=True)
class Entry:
    """A named (or unnamed) reference to a record inside a group."""

    id: int
    group: str
    name: Optional[str]
    record_hash: str
    attrs: Dict[str, Any]
    _dataset: "Dataset" = field(repr=False, compare=False)
    _data: Optional[bytes] = field(default=None, repr=False, compare=False)

    @property
    def path(self) -> Optional[str]:
        if self.name is None:
            return None
        return f"{self.group.rstrip('/')}/{self.name}"

    @property
    def structure(self) -> Structure:
        if self._data is not None:
            return decode(self._data, schema=self._dataset.schema)
        return self._dataset.get(self.record_hash)


@dataclass(frozen=True)
class CheckReport:
    ok: bool
    errors: List[str]
    checked_records: int


def _validate_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    if not isinstance(name, str) or not name or name in (".", ".."):
        raise ValidationError(f"invalid entry name {name!r}")
    if "/" in name or any(ord(c) < 32 for c in name):
        raise ValidationError(f"entry names may not contain '/' or control characters: {name!r}")
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        raise ValidationError(f"entry name longer than {MAX_NAME_BYTES} bytes")
    return name


def _attrs_json(attrs: Optional[Mapping[str, Any]]) -> str:
    value = normalize_json(dict(attrs or {}), path="attrs")
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(text) > MAX_ATTRS_BYTES:
        raise ValidationError(f"attributes exceed {MAX_ATTRS_BYTES} bytes")
    return text


def _split_path(path: str) -> Tuple[str, str]:
    if not path.startswith("/") or path.endswith("/"):
        raise ValidationError(f"entry paths look like '/group/name', got {path!r}")
    group, _, name = path.rpartition("/")
    return normalize_group(group or "/"), _validate_name(name) or ""


def _scalar_values(structure: Structure) -> List[Tuple[str, float]]:
    """Numeric scalar structure properties, indexed for queries."""
    values = []
    for name in structure.properties:
        if structure.properties.dtype(name) == JSON:
            continue
        raw = structure.properties.raw(name)
        if raw.ndim == 0:
            values.append((name, float(raw)))
    return values


def _refuse_pending_wal(path: Path) -> None:
    """Refuse to replace ``path`` while its write-ahead log holds frames.

    Such frames belong to a writer that is still active (or crashed before a
    checkpoint) and must not end up next to a different database file. An
    empty log, as read-only connections leave behind, is harmless.
    """
    wal = Path(f"{path}-wal")
    if wal.exists() and wal.stat().st_size > 0:
        raise DatasetError(
            f"{path} has uncheckpointed changes in {wal}; close its writers "
            "(or open it once in 'a' mode to recover) before replacing it"
        )


class Dataset:
    """A ``.usifc`` dataset file.

    Parameters
    ----------
    path:
        Dataset file.
    mode:
        ``"r"`` read-only; ``"a"`` read/write, created if missing (default);
        ``"w"`` start a new dataset that atomically replaces ``path`` on
        :meth:`close` (an exception inside ``with`` leaves ``path`` untouched).
    compression, precision, symmetry, level:
        Record encoding options for structures added with :meth:`add`.
    schema:
        Property schema used when decoding.

    Records are deduplicated by content: adding an identical structure again
    reuses the stored record. Entries ``(group, name)`` point at records;
    several entries may share one record. Instances are thread-safe; several
    processes may read while one writes.
    """

    def __init__(
        self,
        path: Union[str, os.PathLike[str]],
        mode: Mode = "a",
        *,
        compression: str = "zlib",
        level: Optional[int] = None,
        precision: str = "f64",
        symmetry: str = "off",
        schema: Schema = DEFAULT_SCHEMA,
        timeout: float = 30.0,
    ) -> None:
        from usif.version import __version__

        self.path = Path(path)
        self.mode = mode
        self.schema = schema
        self._encode_options: Dict[str, Any] = {
            "compression": compression,
            "level": level,
            "precision": precision,
            "symmetry": symmetry,
        }
        self._lock = threading.RLock()
        self._depth = 0
        self._closed = False
        self._target: Optional[Path] = None
        open_path = self.path
        if mode == "w":
            _refuse_pending_wal(self.path)
            self._target = self.path
            open_path = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        metadata = {
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "creator": f"usif {__version__}",
            "schema_version": str(SCHEMA_VERSION),
        }
        self._open_path = open_path
        self._conn = connect(open_path, "w" if mode == "w" else mode, metadata, timeout)

    # -- lifecycle ------------------------------------------------------------

    def close(self, *, discard: bool = False) -> None:
        """Close the dataset. In ``"w"`` mode the new file replaces the target
        unless ``discard`` is true (then it is deleted)."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._target is not None and not discard:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._conn.execute("PRAGMA journal_mode = DELETE")
            self._conn.close()
            if self._target is not None:
                if discard:
                    self._open_path.unlink(missing_ok=True)
                else:
                    _refuse_pending_wal(self._target)
                    os.replace(self._open_path, self._target)
                    fsync_directory(self._target.parent)

    def __enter__(self) -> "Dataset":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close(discard=exc_type is not None)

    def _require_open(self) -> sqlite3.Connection:
        if self._closed:
            raise DatasetError("dataset is closed")
        return self._conn

    def _require_writable(self) -> sqlite3.Connection:
        conn = self._require_open()
        if self.mode == "r":
            raise DatasetError("dataset is open read-only")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Group writes atomically; nested use creates savepoints."""
        with self._lock:
            conn = self._require_writable()
            savepoint = f"sp{self._depth}"
            conn.execute("BEGIN IMMEDIATE" if self._depth == 0 else f"SAVEPOINT {savepoint}")
            self._depth += 1
            try:
                yield
            except BaseException as exc:
                self._depth -= 1
                self._rollback(conn, savepoint)
                if isinstance(exc, sqlite3.Error):
                    raise DatasetError(f"{self.path}: {exc}") from exc
                raise
            self._depth -= 1
            try:
                conn.execute("COMMIT" if self._depth == 0 else f"RELEASE {savepoint}")
            except sqlite3.Error as exc:  # e.g. disk full while committing
                self._rollback(conn, savepoint)
                raise DatasetError(f"{self.path}: {exc}") from exc

    def _rollback(self, conn: sqlite3.Connection, savepoint: str) -> None:
        """Undo the innermost transaction level; never mask the error that caused it.

        SQLite rolls back by itself after some failures (I/O errors, a full
        disk), in which case there is nothing left to undo.
        """
        if not conn.in_transaction:
            return
        try:
            if self._depth == 0:
                conn.execute("ROLLBACK")
            else:
                conn.execute(f"ROLLBACK TO {savepoint}")
                conn.execute(f"RELEASE {savepoint}")
        except sqlite3.Error:
            if self._depth == 0 and conn.in_transaction:
                conn.rollback()

    # -- writing --------------------------------------------------------------

    def add(
        self,
        structure: Structure,
        name: Optional[str] = None,
        group: str = "/",
        attrs: Optional[Mapping[str, Any]] = None,
        *,
        overwrite: bool = False,
    ) -> Entry:
        """Store ``structure`` and create (or update) the entry ``group/name``.

        Without a name, adding the same record to the same group again returns
        the existing entry (with ``attrs`` replaced if given). With a name, an
        existing entry is an error unless ``overwrite`` is true.
        """
        data, info = encode_with_info(structure, **self._encode_options)
        return self._insert(data, info, structure, name, group, attrs, overwrite)

    def add_record(
        self,
        data: bytes,
        name: Optional[str] = None,
        group: str = "/",
        attrs: Optional[Mapping[str, Any]] = None,
        *,
        overwrite: bool = False,
    ) -> Entry:
        """Store an already encoded format-7 record (validated by decoding it)."""
        structure, info = decode_with_info(data, schema=self.schema)
        return self._insert(bytes(data), info, structure, name, group, attrs, overwrite)

    def add_many(
        self,
        structures: Iterable[Structure],
        group: str = "/",
        *,
        names: Optional[Iterable[Optional[str]]] = None,
        attrs: Optional[Mapping[str, Any]] = None,
        batch_size: int = PAGE_SIZE,
    ) -> int:
        """Add many structures, committing every ``batch_size``; returns the count."""
        name_iter = iter(names) if names is not None else None
        count = 0
        batch: List[Tuple[bytes, RecordInfo, Structure, Optional[str]]] = []

        def flush() -> None:
            with self.transaction():
                for data, info, structure, name in batch:
                    self._insert(data, info, structure, name, group, attrs, False)
            batch.clear()

        for structure in structures:
            name = next(name_iter) if name_iter is not None else None
            data, info = encode_with_info(structure, **self._encode_options)
            batch.append((data, info, structure, name))
            count += 1
            if len(batch) >= batch_size:
                flush()
        if batch:
            flush()
        return count

    def _insert(
        self,
        data: bytes,
        info: RecordInfo,
        structure: Structure,
        name: Optional[str],
        group: str,
        attrs: Optional[Mapping[str, Any]],
        overwrite: bool,
    ) -> Entry:
        group = normalize_group(group)
        name = _validate_name(name)
        attrs_text = _attrs_json(attrs) if attrs is not None else None
        with self.transaction():
            record_id = self._ensure_record(self._conn, data, info, structure)
            return self._put_entry(record_id, info.record_hash, name, group, attrs_text, overwrite)

    def _put_entry(
        self,
        record_id: int,
        record_hash: str,
        name: Optional[str],
        group: str,
        attrs_text: Optional[str],
        overwrite: bool,
    ) -> Entry:
        """Create or update the entry ``group/name`` for a stored record (inside a transaction)."""
        conn = self._conn
        self._ensure_group(conn, group)
        if name is None:
            row = conn.execute(
                "SELECT id FROM entries WHERE grp = ? AND name IS NULL AND record_id = ?",
                (group, record_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM entries WHERE grp = ? AND name = ?", (group, name)
            ).fetchone()
            if row is not None and not overwrite:
                raise DatasetError(f"entry {group.rstrip('/')}/{name} already exists")
        if row is None:
            entry_id, final_attrs = conn.execute(
                "INSERT INTO entries(grp, name, record_id, attrs) VALUES (?, ?, ?, ?) "
                "RETURNING id, attrs",
                (group, name, record_id, attrs_text or "{}"),
            ).fetchone()
        else:
            entry_id, final_attrs = conn.execute(
                "UPDATE entries SET record_id = ?, attrs = COALESCE(?, attrs) WHERE id = ? "
                "RETURNING id, attrs",
                (record_id, attrs_text, row[0]),
            ).fetchone()
        return Entry(int(entry_id), group, name, record_hash, json.loads(final_attrs), self)

    def link(
        self,
        source: str,
        name: str,
        group: str = "/",
        attrs: Optional[Mapping[str, Any]] = None,
        *,
        overwrite: bool = False,
    ) -> Entry:
        """Create the entry ``group/name`` for the record of the entry at path ``source``.

        Nothing is re-encoded or copied: both entries refer to the same stored
        record, so a structure can appear in several groups (a project and the
        group it was imported into) for the size of one. ``attrs`` default to
        a copy of the source entry's attributes.
        """
        group = normalize_group(group)
        name = _validate_name(name)
        if name is None:
            raise ValidationError("link() needs an entry name")
        with self.transaction():
            entry = self.entry(source)
            row = self._conn.execute(
                "SELECT record_id FROM entries WHERE id = ?", (entry.id,)
            ).fetchone()
            if row is None:
                raise KeyError(entry.path)
            text = _attrs_json(entry.attrs if attrs is None else attrs)
            return self._put_entry(int(row[0]), entry.record_hash, name, group, text, overwrite)

    @staticmethod
    def _ensure_record(
        conn: sqlite3.Connection, data: bytes, info: RecordInfo, structure: Structure
    ) -> int:
        digest = bytes.fromhex(info.record_hash)
        row = conn.execute("SELECT id FROM records WHERE hash = ?", (digest,)).fetchone()
        if row is not None:
            return int(row[0])
        (record_id,) = conn.execute(
            "INSERT INTO records(hash, geometry_hash, data, natoms, formula, chemsys, "
            "periodic, symmetric, nbytes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                digest,
                bytes.fromhex(info.geometry_hash),
                data,
                structure.natoms,
                structure.reduced_formula,
                structure.chemical_system,
                int(structure.is_periodic),
                int(info.symmetric),
                len(data),
            ),
        ).fetchone()
        conn.executemany(
            "INSERT INTO record_elements(record_id, z, count) VALUES (?, ?, ?)",
            [
                (record_id, atomic_number(symbol), n)
                for symbol, n in structure.element_counts.items()
            ],
        )
        conn.executemany(
            "INSERT INTO record_values(record_id, name, value) VALUES (?, ?, ?)",
            [(record_id, name, value) for name, value in _scalar_values(structure)],
        )
        return int(record_id)

    @staticmethod
    def _ensure_group(conn: sqlite3.Connection, group: str) -> None:
        parts = [p for p in group.split("/") if p]
        paths = ["/"] + ["/" + "/".join(parts[: i + 1]) for i in range(len(parts))]
        conn.executemany("INSERT OR IGNORE INTO groups(path) VALUES (?)", [(p,) for p in paths])

    def remove(self, target: Union[str, Entry]) -> None:
        """Remove an entry (records are reclaimed by :meth:`compact`)."""
        entry_id = target.id if isinstance(target, Entry) else self.entry(target).id
        with self.transaction():
            self._conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))

    def set_attrs(
        self, target: Union[str, Entry], attrs: Mapping[str, Any], *, merge: bool = True
    ) -> Dict[str, Any]:
        entry = target if isinstance(target, Entry) else self.entry(target)
        new = {**entry.attrs, **dict(attrs)} if merge else dict(attrs)
        text = _attrs_json(new)
        with self.transaction():
            self._conn.execute("UPDATE entries SET attrs = ? WHERE id = ?", (text, entry.id))
        return json.loads(text)

    def set_group_attrs(
        self, group: str, attrs: Mapping[str, Any], *, merge: bool = True
    ) -> Dict[str, Any]:
        group = normalize_group(group)
        with self.transaction():
            self._ensure_group(self._conn, group)
            current = self.group_attrs(group) if merge else {}
            text = _attrs_json({**current, **dict(attrs)})
            self._conn.execute("UPDATE groups SET attrs = ? WHERE path = ?", (text, group))
        return json.loads(text)

    def import_v2(self, source: Union[str, os.PathLike[str]], *, group: str = "/") -> int:
        """Copy every entry of a USIF 0.8 (v2) container into this dataset.

        Groups are recreated below ``group``, names and attributes are kept,
        and format-5/6 records are decoded (geometry hashes verified) and
        stored as format-7 records. All of it happens in one transaction.
        Returns the number of entries imported.
        """
        from usif.upgrade.container_v2 import open_container_v2
        from usif.upgrade.format6 import decode as decode_format6

        prefix = normalize_group(group)

        def target(path: str) -> str:
            return normalize_group(f"{prefix}/{path}")

        count = 0
        with open_container_v2(source) as container, self.transaction():
            for entry in container:
                structure = decode_format6(
                    container.record_bytes(entry.record_hash), schema=self.schema
                )
                self.add(structure, entry.name, target(entry.group), entry.attrs or None)
                count += 1
            for path, attrs in container.group_attrs.items():
                if attrs:
                    self.set_group_attrs(target(path), attrs)
        return count

    # -- reading --------------------------------------------------------------

    def _fetch(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
        with self._lock:
            return self._require_open().execute(sql, params).fetchall()

    def _entry_from_row(self, row: Tuple[Any, ...]) -> Entry:
        data = bytes(row[5]) if len(row) > 5 and row[5] is not None else None
        return Entry(
            int(row[0]), row[1], row[2], bytes(row[3]).hex(), json.loads(row[4]), self, data
        )

    def get(self, key: Union[str, Entry]) -> Structure:
        """Structure by entry path (``"/group/name"``), record hash or :class:`Entry`."""
        if isinstance(key, Entry):
            key = key.record_hash
        if key.startswith("/"):
            key = self.entry(key).record_hash
        try:
            digest = bytes.fromhex(key)
        except ValueError:
            raise KeyError(key) from None
        rows = self._fetch("SELECT data FROM records WHERE hash = ?", (digest,))
        if not rows:
            raise KeyError(key)
        return decode(rows[0][0], schema=self.schema)

    def __getitem__(self, key: str) -> Structure:
        return self.get(key)

    def entry(self, path: str) -> Entry:
        group, name = _split_path(path)
        rows = self._fetch(
            "SELECT e.id, e.grp, e.name, r.hash, e.attrs FROM entries e "
            "JOIN records r ON r.id = e.record_id WHERE e.grp = ? AND e.name = ?",
            (group, name),
        )
        if not rows:
            raise KeyError(path)
        return self._entry_from_row(rows[0])

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            if key.startswith("/"):
                self.entry(key)
                return True
            return bool(self._fetch("SELECT 1 FROM records WHERE hash = ?", (bytes.fromhex(key),)))
        except (KeyError, ValueError, ValidationError):
            return False

    def query(
        self, where: Optional[Q] = None, *, limit: Optional[int] = None, load: bool = False
    ) -> Iterator[Entry]:
        """Entries matching ``where`` in insertion order, streamed page by page.

        With ``load=True`` record bytes are fetched with the entries, so
        ``entry.structure`` needs no further query.
        """
        where = where or Q.all()
        columns = "e.id, e.grp, e.name, r.hash, e.attrs" + (", r.data" if load else "")
        # Q.sql is fixed SQL text from usif.dataset.query; all values are bound.
        sql = f"SELECT {columns} {_FROM} WHERE e.id > ? AND ({where.sql}) ORDER BY e.id LIMIT ?"  # nosec B608
        last_id = 0
        remaining = limit
        while remaining is None or remaining > 0:
            page = PAGE_SIZE if remaining is None else min(PAGE_SIZE, remaining)
            rows = self._fetch(sql, (last_id, *where.params, page))
            for row in rows:
                yield self._entry_from_row(row)
            if len(rows) < page:
                return
            last_id = rows[-1][0]
            if remaining is not None:
                remaining -= len(rows)

    def structures(self, where: Optional[Q] = None) -> Iterator[Structure]:
        for entry in self.query(where, load=True):
            yield entry.structure

    def count(self, where: Optional[Q] = None) -> int:
        where = where or Q.all()
        rows = self._fetch(f"SELECT COUNT(*) {_FROM} WHERE {where.sql}", where.params)  # nosec B608
        return int(rows[0][0])

    def __len__(self) -> int:
        return self.count()

    def __iter__(self) -> Iterator[Entry]:
        return self.query()

    def groups(self) -> List[str]:
        return [row[0] for row in self._fetch("SELECT path FROM groups ORDER BY path")]

    def group_attrs(self, group: str) -> Dict[str, Any]:
        rows = self._fetch("SELECT attrs FROM groups WHERE path = ?", (normalize_group(group),))
        if not rows:
            raise KeyError(group)
        return dict(json.loads(rows[0][0]))

    def metadata(self) -> Dict[str, str]:
        return {key: value for key, value in self._fetch("SELECT key, value FROM meta")}

    # -- maintenance ------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        # Table names below are literals, not input.
        entries, records, groups = (
            self._fetch(f"SELECT COUNT(*) FROM {table}")[0][0]  # nosec B608
            for table in ("entries", "records", "groups")
        )
        atoms, record_bytes = self._fetch("SELECT TOTAL(natoms), TOTAL(nbytes) FROM records")[0]
        orphans = self._fetch(
            "SELECT COUNT(*) FROM records WHERE id NOT IN (SELECT record_id FROM entries)"
        )[0][0]
        formulas = self._fetch("SELECT COUNT(DISTINCT formula) FROM records")[0][0]
        return {
            "entries": entries,
            "records": records,
            "unreferenced_records": orphans,
            "groups": groups,
            "formulas": formulas,
            "atoms": int(atoms),
            "record_bytes": int(record_bytes),
            "file_bytes": sum(
                path.stat().st_size
                for path in (self._open_path, Path(f"{self._open_path}-wal"))
                if path.exists()
            ),
        }

    def check(self, *, full: bool = False, max_errors: int = 100) -> CheckReport:
        """Verify database integrity; with ``full`` also decode and re-hash every record."""
        errors: List[str] = []
        result = self._fetch("PRAGMA integrity_check")
        if [r[0] for r in result] != ["ok"]:
            errors.extend(f"sqlite: {r[0]}" for r in result[:max_errors])
        for row in self._fetch("PRAGMA foreign_key_check"):
            errors.append(f"foreign key violation: {row}")
        checked = 0
        if full:
            last_id = 0
            while len(errors) < max_errors:
                rows = self._fetch(
                    "SELECT id, hash, geometry_hash, data, natoms, formula FROM records "
                    "WHERE id > ? ORDER BY id LIMIT ?",
                    (last_id, PAGE_SIZE),
                )
                if not rows:
                    break
                for rid, digest, geometry, data, natoms, formula in rows:
                    checked += 1
                    try:
                        structure, info = decode_with_info(data, schema=self.schema)
                    except FormatError as exc:
                        errors.append(f"record {rid}: {exc}")
                        continue
                    if info.record_hash != bytes(digest).hex():
                        errors.append(f"record {rid}: content hash mismatch")
                    if info.geometry_hash != bytes(geometry).hex():
                        errors.append(f"record {rid}: geometry hash mismatch")
                    if structure.natoms != natoms or structure.reduced_formula != formula:
                        errors.append(f"record {rid}: index columns disagree with the record")
                last_id = rows[-1][0]
        return CheckReport(not errors, errors[:max_errors], checked)

    def compact(self) -> int:
        """Delete unreferenced records and rebuild the file; returns bytes reclaimed."""
        with self._lock:
            self._require_writable()
            if self._depth:
                raise DatasetError("compact() cannot run inside a transaction")
            before = self._open_path.stat().st_size
            with self.transaction():
                self._conn.execute(
                    "DELETE FROM records WHERE id NOT IN (SELECT record_id FROM entries)"
                )
                self._conn.execute(
                    "DELETE FROM groups WHERE path != '/' AND path NOT IN "
                    "(SELECT grp FROM entries) AND attrs = '{}' AND NOT EXISTS "
                    "(SELECT 1 FROM entries e WHERE e.grp LIKE groups.path || '/%')"
                )
            self._conn.execute("VACUUM")
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            return max(0, before - self._open_path.stat().st_size)

    def __repr__(self) -> str:
        state = "closed" if self._closed else self.mode
        return f"Dataset({str(self.path)!r}, {state})"
