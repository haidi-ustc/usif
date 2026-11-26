"""SQLite schema and connection management for ``.usifc`` datasets.

A dataset is an SQLite 3 database identified by ``PRAGMA application_id =
0x55534946`` ("USIF") and versioned by ``PRAGMA user_version``. Records are
format-7 ``.usif`` blobs; the other tables index them.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Literal

from usif.errors import DatasetError, UnsupportedVersionError
from usif.version import DATASET_SCHEMA_VERSION

__all__ = ["APPLICATION_ID", "SCHEMA_VERSION", "Mode", "connect"]

APPLICATION_ID = 0x55534946
SCHEMA_VERSION = DATASET_SCHEMA_VERSION

Mode = Literal["r", "a", "w"]

SCHEMA = """
CREATE TABLE meta(
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE records(
    id            INTEGER PRIMARY KEY,
    hash          BLOB NOT NULL UNIQUE,
    geometry_hash BLOB NOT NULL,
    data          BLOB NOT NULL,
    natoms        INTEGER NOT NULL,
    formula       TEXT NOT NULL,
    chemsys       TEXT NOT NULL,
    periodic      INTEGER NOT NULL,
    symmetric     INTEGER NOT NULL,
    nbytes        INTEGER NOT NULL
);
CREATE INDEX records_geometry ON records(geometry_hash);
CREATE INDEX records_formula ON records(formula);
CREATE INDEX records_chemsys ON records(chemsys);
CREATE INDEX records_natoms ON records(natoms);

CREATE TABLE record_elements(
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    z         INTEGER NOT NULL,
    count     INTEGER NOT NULL,
    PRIMARY KEY (z, record_id)
) WITHOUT ROWID;

CREATE TABLE record_values(
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    value     REAL NOT NULL,
    PRIMARY KEY (record_id, name)
) WITHOUT ROWID;
CREATE INDEX record_values_lookup ON record_values(name, value);

CREATE TABLE groups(
    path  TEXT PRIMARY KEY,
    attrs TEXT NOT NULL DEFAULT '{}'
) WITHOUT ROWID;

CREATE TABLE entries(
    id        INTEGER PRIMARY KEY,
    grp       TEXT NOT NULL REFERENCES groups(path),
    name      TEXT,
    record_id INTEGER NOT NULL REFERENCES records(id),
    attrs     TEXT NOT NULL DEFAULT '{}',
    UNIQUE (grp, name)
);
CREATE INDEX entries_record ON entries(record_id);
"""


#: Page cache per connection (KiB) and memory-mapped read window (bytes). Queries join
#: entries to records, whose pages hold the record bytes; with SQLite's 2 MB default cache
#: a 200k-entry dataset re-reads them from the OS on every query (measured 20-50x slower).
CACHE_KIB = 64 * 1024
MMAP_BYTES = 1 << 30


def _configure(conn: sqlite3.Connection, writable: bool) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA cache_size = -{CACHE_KIB}")
    conn.execute(f"PRAGMA mmap_size = {MMAP_BYTES}")
    if writable:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")


def _initialise(conn: sqlite3.Connection, metadata: dict[str, str]) -> None:
    conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    conn.execute("BEGIN")
    for statement in SCHEMA.split(";"):
        if statement.strip():
            conn.execute(statement)
    conn.execute("INSERT INTO groups(path) VALUES ('/')")
    conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", sorted(metadata.items()))
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.execute("COMMIT")


def _verify(conn: sqlite3.Connection, path: Path) -> None:
    try:
        app_id = conn.execute("PRAGMA application_id").fetchone()[0]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise DatasetError(
            f"{path} is not a USIF dataset ({exc}); a container written by USIF 0.8 or "
            "earlier is copied into a dataset with Dataset.import_v2"
        ) from exc
    if app_id != APPLICATION_ID:
        raise DatasetError(f"{path} is an SQLite database but not a USIF dataset")
    if version != SCHEMA_VERSION:
        raise UnsupportedVersionError(
            f"{path} uses dataset schema {version}; this USIF reads schema {SCHEMA_VERSION}"
        )


def connect(path: Path, mode: Mode, metadata: dict[str, str], timeout: float) -> sqlite3.Connection:
    """Open (and for new files create) a dataset database.

    ``mode``: ``"r"`` read-only, ``"a"`` read/write (create if missing),
    ``"w"`` create a new, empty dataset (the caller handles replacement).
    """
    if mode not in ("r", "a", "w"):
        raise DatasetError(f"mode must be 'r', 'a' or 'w', got {mode!r}")
    exists = path.exists() and path.stat().st_size > 0
    if mode == "r" and not exists:
        raise DatasetError(f"dataset {path} does not exist")
    if mode == "w" and path.exists():
        raise DatasetError(f"refusing to initialise over existing file {path}")
    try:
        if mode == "r":
            uri = f"{path.resolve().as_uri()}?mode=ro"
            conn = sqlite3.connect(
                uri, uri=True, timeout=timeout, isolation_level=None, check_same_thread=False
            )
        else:
            conn = sqlite3.connect(
                os.fspath(path), timeout=timeout, isolation_level=None, check_same_thread=False
            )
    except sqlite3.Error as exc:
        raise DatasetError(f"cannot open dataset {path}: {exc}") from exc
    try:
        if exists:
            _verify(conn, path)
            _configure(conn, writable=mode != "r")
        else:
            _configure(conn, writable=True)
            _initialise(conn, metadata)
    except BaseException:
        conn.close()
        raise
    return conn
