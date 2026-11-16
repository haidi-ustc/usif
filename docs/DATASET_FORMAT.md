# The `.usifc` dataset

A dataset stores many structures: deduplicated, organised in groups, annotated with JSON
attributes, and indexed for queries. It is an SQLite 3 database, so any SQLite tool can open it,
and transactions, crash safety and concurrent readers come from SQLite rather than from USIF
code. `usif.dataset` implements it. Version-2 containers written by USIF 0.8 are described in
[FORMATS_0_8.md](FORMATS_0_8.md).

## 1. Identification

| Item | Value |
|---|---|
| `PRAGMA application_id` | `0x55534946` ("USIF") |
| `PRAGMA user_version` | dataset schema version, currently `1` |
| journal | WAL while open for writing (`synchronous = NORMAL`); `"w"` mode switches the finished file to `DELETE` |
| foreign keys | enforced |

A reader refuses files with another application id, and schema versions it does not know.

## 2. Tables

```sql
meta(key TEXT PRIMARY KEY, value TEXT)              -- created, creator, schema_version

records(
  id            INTEGER PRIMARY KEY,
  hash          BLOB UNIQUE,      -- record_hash, 32 bytes
  geometry_hash BLOB,             -- 32 bytes, indexed
  data          BLOB,             -- a complete format-7 .usif record
  natoms        INTEGER,          -- indexed
  formula       TEXT,             -- reduced formula, indexed
  chemsys       TEXT,             -- sorted element set "Cl-Na", indexed
  periodic      INTEGER,
  symmetric     INTEGER,          -- 1 if the record stores a SYMM section
  nbytes        INTEGER)

record_elements(record_id, z, count)       -- PRIMARY KEY (z, record_id)
record_values(record_id, name, value REAL) -- numeric scalar structure properties, indexed (name, value)

groups(path TEXT PRIMARY KEY, attrs TEXT)  -- "/" and "/a/b", attrs is a JSON object
entries(
  id        INTEGER PRIMARY KEY,
  grp       TEXT REFERENCES groups(path),
  name      TEXT,                          -- NULL for unnamed entries; UNIQUE (grp, name)
  record_id INTEGER REFERENCES records(id),
  attrs     TEXT)                          -- JSON object
```

The columns of `records` other than `data`, and the two side tables, are derived from the record
when it is added. `Dataset.check(full=True)` decodes every record and verifies that its hashes
and index columns still agree.

## 3. Semantics

* **Records** are immutable and deduplicated by `record_hash`. Adding identical content again
  reuses the row.
* **Entries** name records. An entry is `(group, name)` with JSON attributes; several entries may
  share one record. Unnamed entries are unique per `(group, record)`.
* **Groups** are slash paths. Adding to `/a/b` creates `/a` and `/a/b`. Group attributes are a JSON
  object.
* Removing an entry leaves its record in place until `compact()` deletes unreferenced records and
  empty attribute-less groups, then runs `VACUUM`.
* All JSON (attributes, JSON columns) is canonical: sorted keys, no NaN or Infinity.

## 4. Queries

`usif.dataset.Q` builds `WHERE` clauses over `entries e JOIN records r`. Every user value, and every
property or attribute name, is bound as an SQL parameter; the SQL text comes only from fixed
templates in `usif/dataset/query.py`.

| Condition | Uses |
|---|---|
| `Q.formula`, `Q.chemsys`, `Q.natoms`, `Q.periodic`, `Q.geometry`, `Q.record` | indexed `records` columns |
| `Q.elements(*symbols)` | `record_elements` |
| `Q.prop(name) < x`, `Q.has_prop(name)` | `record_values` |
| `Q.group(path, recursive=True)`, `Q.name(glob)` | `entries` |
| `Q.attr(key) == v`, `Q.has_attr(key)` | `json_extract` on `entries.attrs` |

Conditions combine with `&`, `|` and `~`. `Dataset.query()` streams results in pages ordered by
entry id, so memory use does not grow with the dataset.

## 5. Concurrency and durability

* Writes go through transactions (`Dataset.transaction()`, nested as savepoints). `add_many`
  commits in batches.
* In WAL mode any number of readers, in this or other processes, can read while one writer writes.
* `Dataset(path, "w")` builds a new file next to the target and atomically replaces the target on
  a clean close; an exception inside `with` leaves the old file untouched. It refuses to replace a
  file whose write-ahead log still holds frames.
* A `Dataset` object is safe to share between threads.
