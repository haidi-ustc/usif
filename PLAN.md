# USIF 0.9 architecture redesign

Status: **in progress** on branch `refactor/0.9-architecture`.
Target release: **0.9.0**. This is a breaking release; the project is pre-1.0, so the minor bump follows the versioning policy.

This document records:

1. why the current architecture is being replaced;
2. the target design;
3. the file-format specifications;
4. the work plan.

---

## 1. Analysis of the 0.8 architecture

### 1.1 Measured cost of the data model

The test case is a 20,000-atom crystal with forces and charges.

| Metric | 0.8 | Flat-array lower bound |
|---|---|---|
| In-memory model | 822 B/atom | ~57 B/atom (Z + 2×(3×f64) + f64) |
| Encoded record, uncompressed | 146 B/atom (with float32 coordinates) | ~57 B/atom with float64 coordinates |
| Build model from arrays | 2.5 s | milliseconds |
| Decode | 1.3 s | milliseconds (`np.frombuffer`) |

The causes:

- Every atom is an `AtomSite` object that owns an `AtomicProperties` object, with a value dict and a units dict.
- The binary format writes a property section **per atom**, repeating each property name and its length prefix for every atom.

### 1.2 Structural problems

| # | Problem | Consequence |
|---|---|---|
| 1 | `StructureType` × `StorageMode` × three site classes (`WyckoffSite`, `PointGroupSite`, `AtomSite`) in one model, with many optional fields | Invalid states can be constructed (a crystal without a lattice, symmetric sites mixed with per-atom data). Every consumer branches on four cases. |
| 2 | Symmetric storage is a *model state*, not an *encoding* | Every adapter, the policy object and every service must handle it. Expansion reorders atoms, so the order the user gave is lost. |
| 3 | Decoding depends on the reader's `PropertyRegistry` ("known" vs "custom" properties) | The same bytes mean different things under different registries. Records are not self-describing. |
| 4 | Two near-identical property containers (`StructureProperties`, `AtomicProperties`), a registry with value-range validation, a value-envelope type and a `__USIF_JSON__:` string prefix: 2,668 lines in total | Duplicated logic and unclear semantics (units per value, per atom, per registry). |
| 5 | Derived data stored as data (`formula`, `volume`) | It can disagree with the geometry. |
| 6 | Three hash schemes with float32 canonicalisation, count escaping and "setting only if non-default" rules | Hard to specify and to verify independently. A record hash requires a full encode → decode round trip. |
| 7 | Container: a hand-written append-only file with chunk allocation, mmap, CRC'd index generations, a commit marker, magic-scanning recovery and five mixins sharing undeclared state (2,507 lines) | The whole index is re-serialised as JSON on every commit (O(N) per flush, quadratic file growth with autocommit). Recovery by magic scan is forgeable. There is no compaction and no real concurrency story. Most of the mypy errors come from here. |
| 8 | Ad-hoc dispatch in `services/convert.py` (try matsimpy, then ASE, then pymatgen) plus three adapter classes plus an intermediate `AtomsData` | Adding a backend means touching several modules. No plugin mechanism. |
| 9 | Coordinates are stored as float32 only | An *interchange* format cannot round-trip its own input. |
| 10 | The payload digest is not in the header; corruption is detected only after decompression, by a geometry-hash comparison | No cheap integrity check. A corrupted record can be decompressed into a large allocation before it is rejected. |

### 1.3 What is kept

- **spglib symmetry engine** (`symmetry/spacegroup.py`, `expand.py`, `reduce.py`, `tables.py`): Hall numbers, `(P, p)` settings, lossless gate. It is re-targeted at the new model.
- **Core-owned element table and reduced formula** (`elements.py`, `formula.py`).
- **Atomic file replacement** (`fileio.py`).
- **Backend mapping knowledge** in the matsimpy, pymatgen and ASE adapters: oxidation states, molecule charge and spin, ASE stress and velocity units, disorder rejection.
- **Materials Project tooling** (downloader, archive, loader). The mapper is re-targeted.
- **Format-5/6 golden fixtures.** They become migration tests.

---

## 2. Design principles

1. **Structure of arrays.** A structure is a handful of numpy arrays. Per-atom data is a column, never an object per atom.
2. **One model, no modes.** The model always holds the full structure. Compact symmetric storage is an encoding option of the record codec, invisible to everything else.
3. **Self-describing, deterministic records.** Every value carries its name, dtype, shape and unit in the record. The same structure and options always produce the same bytes, so identity hashes are hashes of bytes.
4. **Use proven infrastructure.** The multi-record dataset is an SQLite database (stdlib, ACID, concurrent readers, indexes, `VACUUM`). It replaces the hand-written container.
5. **Explicit extension points:**
   - compression codecs;
   - record sections;
   - property specs;
   - structure backends;
   - file formats.

   Each is a small registry with a clear protocol. Nothing beyond that (no plugin framework, no abstract base class for things with one implementation).
6. **Untrusted-input discipline:**
   - bounds-checked reads;
   - size limits checked before allocation;
   - checksum verified before decompression;
   - decompression capped at the declared size;
   - a whitelist of dtypes;
   - JSON only (never pickle);
   - parameterised SQL only.

---

## 3. Module design

### 3.1 Layout

```text
usif/
  __init__.py          public API (lazy for dataset/backends): Structure, Cell, read, write,
                       convert, encode, decode, Dataset, Q, errors
  version.py           package/release metadata, FORMAT_VERSION, DATASET_SCHEMA_VERSION
  errors.py            exception hierarchy
  elements.py          element table (Z, symbol, electronegativity)
  formula.py           full/reduced formula, element counts, chemical system
  units.py             unit-string normalisation, conversion constants
  fileio.py            atomic file replacement

  model/               WHAT a structure is
    cell.py            Cell: immutable lattice matrix + pbc, fractional/Cartesian maps
    properties.py      PropertySpec, Schema, PropertyMap, JSON normalisation
    structure.py       Structure: numbers, positions, cell, arrays, properties

  symmetry/            HOW a periodic structure is reduced/expanded (spglib)
    spacegroup.py      spglib analysis, Hall settings, operations in the stored basis
    reduce.py          Structure -> SymmetricForm | None (lossless gate)
    expand.py          SymmetricForm -> numbers, fractional positions, atom order
    tables.py          frozen format-5 space-group -> Hall and point-group tables

  codec/               HOW one structure becomes bytes (current formats only)
    wire.py            ByteReader / ByteWriter: bounds-checked primitives on memoryview
    compression.py     Compressor protocol + registry (none, zlib, lzma, zstd*)
    columns.py         property-column encoding shared by ARRS and PROP (dtype codes)
    record.py          format-7 record: header, sections, encode/decode, RecordInfo
    jsondoc.py         JSON document usif.structure.json.v2

  dataset/             HOW many records are stored and queried (.usifc, SQLite)
    sql.py             DDL, schema version, connection setup (pragmas, application_id)
    dataset.py         Dataset, Entry: add/get/iterate/groups/attrs/stats/check/compact
    query.py           Q expression builder -> parameterised SQL

  upgrade/             frozen readers for EARLIER formats, nothing else uses their internals
    format6.py         .usif format 5/6 record -> Structure
    container_v2.py    .usifc v2 container -> iterator of (group, name, attrs, Structure)

  backends/            HOW structures cross into other libraries
    base.py            Backend protocol, ordered registry, entry-point discovery
    matsimpy.py  pymatgen.py  ase.py

  io.py                read/write/convert: native suffixes -> codec, older records -> upgrade,
                       everything else -> first capable backend
  cli.py               Typer CLI over io, dataset and upgrade
  (benchmarks and Materials Project tooling live in scripts/, outside the package)
```

### 3.2 Responsibilities and allowed imports

| Module | Owns | May import (inside usif) | Must not import |
|---|---|---|---|
| `errors`, `elements`, `formula`, `units`, `fileio` | domain basics | each other only | everything else |
| `model` | the data model and its invariants | basics | symmetry, codec, dataset, upgrade, backends, io |
| `symmetry` | spglib reduction/expansion | basics, model | codec, dataset, backends, io |
| `codec` | current byte formats and identity hashes | basics, model, symmetry | dataset, upgrade, backends, io |
| `upgrade` | reading earlier formats (frozen) | basics, model, symmetry, codec.wire | dataset internals, backends, io |
| `dataset` | multi-record storage, indexing, queries | basics, model, codec, upgrade (migration only) | backends, io |
| `backends` | mapping to/from external libraries | basics, model | codec, dataset, io |
| `io` | user-facing single-structure I/O dispatch | model, codec, upgrade, backends | dataset |
| `cli` | the command line | everything above | private members of other packages |

- Optional libraries (matsimpy, pymatgen, ASE, zstandard, mp-api) are imported only inside the module that needs them, at call time.
- An import-graph test enforces this table.

### 3.3 Extension points

There are exactly four, each a small registry:

| Extension point | Registry | Registration |
|---|---|---|
| Property specs | `Schema.register(spec, per_atom=...)`; a `Schema` is passed to `Structure`/`decode` | code |
| Compression codecs | `codec.compression.register(Compressor)` (stable one-byte ids) | code |
| Structure backends, including foreign file formats | `backends.register(Backend)` | code or the entry-point group `usif.backends` |
| Record format | ancillary (lower-case) section tags are skipped by readers that do not know them | specification |

Rejected:

- A section plug-in registry: user data extends through self-describing property columns instead.
- Pluggable dataset storage engines: one well-specified SQLite schema is the dataset format.

### 3.4 Dependency graph

```text
errors, elements, formula, units, fileio
              ^
            model <---------------- backends
              ^                        ^
          symmetry                     |
              ^                        |
            codec <---- upgrade        |
              ^            ^           |
           dataset --------+           |
              ^                        |
             cli ------> io -----------+
```

## 4. Data model

```python
Structure(
    numbers,             # (N,) atomic numbers, stored as uint8 (1..118)
    positions,           # (N, 3) float64 Cartesian Å
    cell=None,           # Cell(matrix (3,3) rows = lattice vectors, pbc=(bool, bool, bool)) or None
    arrays=None,         # per-atom columns: {name: array with leading dimension N}
    properties=None,     # structure-level values: {name: scalar | array | JSON value}
)
```

- **Molecule vs crystal.** `structure.is_periodic` is true when `cell` is set and any `pbc` is true. There is no separate type enum.
- **Derived values** are properties of the object, never stored: `formula`, `reduced_formula`, `volume`, `frac_positions`, `natoms`, `element_counts`.
- **Validation at construction:**
  - shapes, finiteness and the Z range;
  - non-degenerate cells;
  - column lengths equal to N;
  - JSON-compatible structure values.
- **Arrays are owned** (input is copied) and **write-protected**. Changes go through methods, so cached derived data cannot go stale.
- **Units.** `PropertyMap` stores `(value, unit)` per name. The unit defaults from the `Schema` (`energy`: eV, `stress`: GPa (Voigt 6), `force`: eV/Å, `charge`: e, `magmom`: μB, `velocity`: Å/fs, ...). Unit strings are normalised, values are never converted. Unknown names are allowed: their dtype and shape are inferred and their unit is optional.
- **Equality** is exact. `allclose(other, atol)` gives tolerant comparison.

---

## 5. Record format 7 (`.usif`)

```text
Header, 40 bytes:
  magic        8   b"\x89USIF\r\n\x1a"   (detects text-mode mangling, like PNG)
  version      u16 = 7
  flags        u16 (reserved, 0)
  compression  u8  (0 none, 1 zlib, 2 lzma, 3 zstd)
  reserved     3   zero
  raw_size     u64 uncompressed payload size
  stored_size  u64 compressed payload size
  digest       8   first 8 bytes of BLAKE2b-256(stored payload)

Payload (after decompression): sequence of sections
  tag   4 ASCII bytes; an upper-case first letter means critical (a reader must understand it)
  size  u64
  body  size bytes
```

| Tag | Content |
|---|---|
| `ATOM` | `N` u32; Z u8[N] |
| `CELL` | pbc u8 bitmask; matrix f64[9] (absent for molecules) |
| `POSN` | dtype code (f64 or f32); Cartesian positions [N×3] |
| `SYMM` | Alternative to `POSN`: Hall u16; `P` f64[9]; `p` f64[3]; representative count u32; reps (Z u8, multiplicity u32, frac f64[3]); permutation u32[N] restoring the user's atom order |
| `ARRS` | Per-atom columns, sorted by name. Each column: name, unit, dtype code, ndim, dims, raw little-endian data |
| `PROP` | Structure-level values, same column encoding (no atom axis); dtype `json` for arbitrary JSON (UTF-8) |
| lower-case tags | Ancillary sections; readers that do not know them skip them. An unknown upper-case (critical) tag is a `FormatError`. |

Identity:

- `record_hash` = BLAKE2b-256 of the raw payload.
- `geometry_hash` = BLAKE2b-256 of the `ATOM`+`CELL`+`POSN`/`SYMM` section bytes.

Both come from bytes without decoding. They are deterministic because encoding is canonical: fixed section order, sorted columns, fixed dtypes.

Options:

- `precision="f64"` (default, exact) or `"f32"` (compact).
- `symmetry="off"` (default, exact) or `"auto"`. Auto writes `SYMM` when spglib finds a lossless reduction (within 1e-5 Å) and the structure has no per-atom arrays.
- `compression`.

Decoding:

1. Verify the digest **before** decompression.
2. Decompress with a hard cap at `raw_size`.
3. Check every count against the limits before allocating.
4. Read numeric arrays as `np.frombuffer` views and copy them once.

Format-5/6 records: `upgrade.format6` is a frozen, read-only decoder that produces a `Structure`. `usif.read()` uses it transparently, and `usif upgrade` rewrites whole files.

---

## 6. Dataset (`.usifc`, SQLite)

- `PRAGMA application_id = 0x55534946` (the bytes "USIF") identifies the file.
- `PRAGMA user_version` holds the schema version.
- WAL mode is used when the file is local and writable.

The tables and indexes as built are specified in `docs/DATASET_FORMAT.md` (`usif/dataset/sql.py`):
`records` (hash, geometry_hash, data, natoms, reduced formula, chemsys, periodic, symmetric,
nbytes), `record_elements(record_id, z, count)`, `record_values`, `groups`, `entries`, `meta`.

API:

```python
with Dataset("data.usifc", mode="a") as ds:      # "r", "a" (create or append), "w" (truncate)
    ref = ds.add(structure, name="nacl", group="/halides", attrs={"source": "mp"})
    ds.add_many(iterable, group=...)              # one transaction
    s = ds.get(ref) / ds["/halides/nacl"]
    for entry in ds.query(Q.formula("NaCl") & Q.prop("energy") < -10 & Q.elements("Na")):
        entry.structure, entry.name, entry.attrs
    ds.stats(); ds.check(full=True); ds.compact()
```

Behaviour:

- Records are deduplicated by `hash`. Several entries (names) can point to one record.
- Large imports run inside one transaction (`add_many` / `with ds.transaction():`).
- Queries stream from a cursor, and records are decoded only when `.structure` is accessed.
- `check()` runs `PRAGMA integrity_check` and optionally re-hashes every record.
- `compact()` runs `VACUUM` and drops unreferenced records.

---

## 7. Backends and file I/O

```python
class Backend(Protocol):
    name: str
    def accepts(self, obj) -> bool
    def to_structure(self, obj) -> Structure
    def from_structure(self, s: Structure) -> Any
    def read(self, path, format=None) -> list[Structure]       # optional
    def write(self, s, path, format=None) -> None              # optional
```

- The registry is ordered matsimpy → ASE → pymatgen, then entry-point backends. Backends are imported lazily.
- A backend that implements `read`/`write` also provides foreign file formats. There is no separate format registry.
- `usif.read(path_or_obj)`, `usif.write(structure, path, **options)` and `usif.convert(structure, "ase")` are the only single-structure I/O entry points:
  - `.usif` goes to `codec.record`, or to `upgrade.format6` when the header shows format 5 or 6;
  - `.json`/`.usif.json` go to `codec.jsondoc`;
  - everything else goes to the first backend that can handle it;
  - an in-memory object goes to the backend whose `accepts()` is true.

---

## 8. Error hierarchy

```text
USIFError
├── ValidationError (also ValueError)           invalid model input
├── FormatError                                  malformed/unsupported bytes or documents
│   ├── ChecksumError                            digest mismatch
│   └── UnsupportedVersionError
├── DatasetError                                 dataset/SQLite problems, locked, read-only
└── MissingDependencyError (also ImportError)    optional package not installed
```

---

## 9. Work plan

| # | Milestone | Content | Done when |
|---|---|---|---|
| M1 | Foundations | `errors`, `units` (trimmed), `model` (Cell, Structure, properties/Schema) | model unit tests pass |
| M2 | Record codec | `wire`, `dtypes`, `compression`, `record` (format 7), hashes, `jsondoc` | round-trip, determinism, corruption and limit tests |
| M3 | Symmetry | engine re-targeted to `Structure`; `SYMM` section with order permutation | reduce/expand tests, including supercells, shifted origins, 600-atom P-1 |
| M4 | Dataset | SQLite `Dataset`, `Q`, `check`, `compact` | functional, concurrency (threads and processes), corruption tests |
| M5 | Upgrade | `upgrade.format6`, `upgrade.container_v2`, `Dataset.import_v2` | all golden format-5/6 fixtures and the v2 container decode to the expected structures |
| M6 | Backends + I/O | backend protocol and registry; matsimpy/pymatgen/ASE ports; `read`/`write`/`convert` | adapter tests (`importorskip`), same hash across backends |
| M7 | Applications | CLI, Materials Project mapper, benchmarks, examples | CLI and example smoke tests |
| M8 | Cleanup and release | delete the old packages; rewrite docs (ARCHITECTURE, BINARY_FORMAT, DATASET_FORMAT, README, site); CHANGELOG 0.9.0 with a migration guide; release metadata; black/isort/mypy/bandit clean; coverage ≥ 80% | all CI gates green |

Constraints during the work:

- Run one heavy task at a time (machine limit).
- New code must be black-, isort- and mypy-clean from the start.
- The old package stays importable until M8, so each milestone can be compared against the old behaviour (golden fixtures, cross-checks).

## 10. Decisions and trade-offs

- **SQLite instead of a custom container.** We lose a hand-specified byte layout for the dataset. We gain:
  - ACID commits;
  - crash safety;
  - concurrent readers;
  - real indexes and queries;
  - compaction;
  - a file any language can open.

  This removes about 2,500 lines and the forged-index and quadratic-commit problems.
- **Exact by default.** float64 coordinates and no symmetrisation unless asked. Compactness is opt-in (`precision="f32"`, `symmetry="auto"`, `compression="lzma"`/`"zstd"`).
- **Symmetric molecules are not written.** Format-5 symmetric molecules are still read.
- **The JSON v1 document is not read.** Breaking change, documented. `.usif` and `.usifc` files have a migration path.
- **No per-value range validation** in property specs. Shape and dtype are checked; physics plausibility is the caller's job.
