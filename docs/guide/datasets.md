# Datasets (`.usifc`)

A `usif.Dataset` stores many structures in one SQLite 3 file. Each structure is kept as a format-7 record blob (see [Records](records.md)); other tables index the records for queries. The SQLite schema is specified in [DATASET_FORMAT.md](../DATASET_FORMAT.md).

## Records, entries and groups

- A **record** is one encoded structure. Records are deduplicated by `record_hash`: adding identical content again stores nothing new.
- An **entry** points at a record from a **group** and has an optional **name** and JSON **attributes**. Several entries may share one record.
- **Groups** are paths such as `/`, `/train` or `/train/molecules`. Parent groups are created automatically and groups can carry their own attributes.

An entry with a name has a path, `"/group/name"`. Entry names cannot contain `/`. Adding an unnamed structure to a group that already holds the same record returns the existing entry.

## Example

[`examples/02_dataset_workflow.py`](../../examples/02_dataset_workflow.py) stores an equation-of-state scan, queries it and checks it:

```python
import numpy as np
from usif import Cell, Dataset, Q, Structure


def rocksalt(a, energy):
    return Structure.from_fractional(
        ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(a), properties={"energy": energy}
    )


lattice = np.linspace(5.4, 5.9, 11)
energies = 0.5 * (lattice - 5.64) ** 2 - 6.8

with Dataset("scan.usifc", "w", symmetry="auto") as ds:
    ds.add_many(
        (rocksalt(a, e) for a, e in zip(lattice, energies)),
        "/eos",
        names=[f"a={a:.2f}" for a in lattice],
        attrs={"method": "PBE"},
    )
    ds.set_group_attrs("/eos", {"description": "NaCl equation of state"})
    ds.add(rocksalt(lattice[5], energies[5]), "reference", "/ref", attrs={"note": "copy"})
    print(ds.stats()["entries"], ds.stats()["records"])   # 12 11: the copy reuses a record
    ds.link("/eos/a=5.65", "minimum", "/projects/eos")      # one more entry, no new record

with Dataset("scan.usifc", "r") as ds:
    low = Q.group("/eos") & (Q.prop("energy") < -6.79)
    print([e.name for e in ds.query(low)])
    print(ds["/eos/a=5.65"].properties["energy"])
    for entry in ds.query(Q.formula("NaCl"), limit=3, load=True):
        print(entry.path, entry.attrs, entry.structure.cell.lengths[0])

with Dataset("scan.usifc") as ds:
    with ds.transaction():             # all or nothing
        ds.remove("/ref/reference")
        ds.set_attrs("/eos/a=5.65", {"selected": True})
    report = ds.check(full=True)
    print(report.ok, report.checked_records)
    print(ds.compact(), "bytes reclaimed")
```

## Opening

`Dataset(path, mode="a", *, compression="zlib", level=None, precision="f64", symmetry="off", schema=DEFAULT_SCHEMA, timeout=30.0)`

| Mode | Meaning |
|---|---|
| `"a"` (default) | Read and write; the file is created if missing. |
| `"r"` | Read only; writes raise `DatasetError`. |
| `"w"` | Build a new dataset in a temporary file next to the target that replaces it on `close()`. If the `with` block raises, the target is left untouched. |

`compression`, `level`, `precision` and `symmetry` set the record encoding for structures added with `add()`/`add_many()`; `schema` is used when decoding.

## Writing

| Method | Purpose |
|---|---|
| `add(structure, name=None, group="/", attrs=None, *, overwrite=False)` | Store a structure, return its `Entry`. A named entry that exists raises `DatasetError` unless `overwrite=True`. |
| `add_many(structures, group="/", *, names=None, attrs=None, batch_size=1000)` | Add an iterable, committing every `batch_size`; returns the count. |
| `add_record(data, name=None, group="/", attrs=None, *, overwrite=False)` | Store already encoded format-7 bytes (validated by decoding). |
| `link(source, name, group="/", attrs=None, *, overwrite=False)` | Create entry `group/name` for the record of the entry at path `source`; nothing is copied or re-encoded. `attrs` default to a copy of the source entry's. Use it to show one structure in several groups, such as a project. |
| `remove(path_or_entry)` | Delete an entry; the record stays until `compact()`. |
| `set_attrs(path_or_entry, attrs, *, merge=True)` | Update entry attributes. |
| `set_group_attrs(group, attrs, *, merge=True)` | Update group attributes. |
| `transaction()` | Context manager that makes the writes inside it atomic (nests as savepoints). |
| `import_v2(path, *, group="/")` | Copy a USIF 0.8 container in (see [Upgrading](upgrading.md)). |

## Reading

| Method | Purpose |
|---|---|
| `get(key)` / `ds[key]` | Structure by entry path, record hash or `Entry`. |
| `entry(path)` | The `Entry` at `"/group/name"`. |
| `key in ds` | Whether an entry path or record hash exists. |
| `query(where=None, *, limit=None, load=False)` | Matching entries in insertion order, streamed page by page. `load=True` fetches the record bytes with the entries, so `entry.structure` needs no extra query. |
| `structures(where=None)` | Matching structures. |
| `count(where=None)`, `len(ds)`, `iter(ds)` | Count or iterate entries. |
| `groups()`, `group_attrs(group)`, `metadata()` | Group paths, group attributes and file metadata (`created`, `creator`, `schema_version`). |

An `Entry` has `id`, `group`, `name`, `path`, `record_hash`, `attrs` and a `structure` property that decodes the record.

## Queries

`Q` builds conditions that compile to parameterised SQL. Combine them with `&`, `|` and `~`. Record conditions (formula, elements, atom count, properties, hashes) use indexed columns and tables.

| Condition | Matches |
|---|---|
| `Q.formula("NaCl")` | Reduced formula (`Structure.reduced_formula`) |
| `Q.chemsys("Na-Cl")` | Exactly these elements |
| `Q.elements("Fe", "O")` | Contains every listed element |
| `Q.natoms(min=None, max=None)` | Atom count range |
| `Q.periodic(True)` | Periodic or not |
| `Q.prop("energy") < -1.0` | Numeric scalar structure property (`<`, `<=`, `>`, `>=`, `==`, `!=`, `.between(low, high)`) |
| `Q.has_prop("energy")` | Has that numeric scalar property |
| `Q.record(hash)`, `Q.geometry(hash)` | Record or geometry hash |
| `Q.group("/a", recursive=True)` | Entries in a group (and its subgroups) |
| `Q.name("nacl*")` | Entry name glob pattern (`*`, `?`, `[...]`) |
| `Q.attr("source") == "mp"`, `Q.has_attr("source")` | Top-level entry attribute; compare against numbers, strings or booleans |
| `Q.attr("tag").isin(["a", "b"])`, `Q.prop("energy").isin([...])` | One of up to 500 values |
| `Q.all()` | Everything |

Wrap comparisons in parentheses when combining them, because `&` binds tighter than `<`: `Q.group("/a") & (Q.prop("energy") < 0)`.

Attribute conditions read the JSON of every entry they consider (about 150 ms per 200,000
entries); combine them with record or group conditions when you can.

Only numeric 0-d structure properties are indexed for `Q.prop`; arrays, per-atom values and JSON values are not queryable. Store a value you want to filter on as a scalar property or as an entry attribute.

```python
from usif import Cell, Dataset, Q, Structure

with Dataset("demo.usifc", "w") as ds:
    for a, energy in ((5.5, -6.7), (5.64, -6.8), (5.8, -6.75)):
        s = Structure.from_fractional(["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]],
                                      Cell.cubic(a), properties={"energy": energy})
        ds.add(s, f"nacl-{a}", "/salts/rocksalt", attrs={"source": "demo", "a": a})

with Dataset("demo.usifc", "r") as ds:
    # Record conditions
    print(ds.count(Q.chemsys("Na-Cl") & Q.natoms(max=8)))
    print(ds.count(Q.elements("Na") & ~Q.elements("K")))
    print(ds.count(Q.prop("energy").between(-6.8, -6.74)))

    # Entry conditions
    print([e.name for e in ds.query(Q.group("/salts"))])            # includes subgroups
    print([e.name for e in ds.query(Q.group("/salts", recursive=False))])
    print([e.name for e in ds.query(Q.name("nacl-5.[56]*"))])
    print([e.name for e in ds.query((Q.attr("a") > 5.6) | (Q.attr("source") == "other"))])

    # Lowest energy, loading structures with the entries
    best = min(ds.query(Q.has_prop("energy"), load=True),
               key=lambda e: e.structure.properties["energy"])
    print(best.path)
```

To find other entries with the same geometry, use `Q.geometry(info.geometry_hash)` with `info` from `usif.codec.encode_with_info`.

## Checking and maintenance

- `stats()`: counts of `entries`, `records`, `unreferenced_records`, `groups`, distinct `formulas` and `atoms`, plus `record_bytes` and `file_bytes`.
- `check(full=False)`: SQLite integrity and foreign-key checks; with `full=True` every record is also decoded and its hashes and index columns are compared. Returns a `CheckReport(ok, errors, checked_records)`.
- `compact()`: deletes unreferenced records and empty groups without attributes, runs `VACUUM`, and returns the bytes reclaimed. It cannot run inside `transaction()`.

`remove()` deletes entries but keeps their records, so other entries sharing a record are unaffected; `compact()` reclaims the space.

From the shell: `usif validate data.usifc --full` (exit code 1 if anything is wrong) and `usif dataset compact data.usifc`; see [Command line](command-line.md).

## Size and speed

One SQLite file serves a research group's dataset well. Measured on a 200,000-entry dataset
(216 MB, 4–15 atoms per structure, provenance attributes on every entry):

| Operation | Time |
|---|---|
| `count()` of everything | 29 ms |
| `Q.formula(...)`, `Q.prop("energy") < x` | 5–10 ms |
| `Q.elements("Fe", "O")` | 58 ms |
| `Q.group("/proj7")` (4,000 entries) | 28 ms |
| `Q.attr("code") == "vasp"` (JSON attribute, scans entries) | 157 ms |
| first 20 matches with structures decoded | 67 ms |
| adding structures | about 1,300 per second |

Connections use a 64 MiB page cache and memory-mapped reads (`usif.dataset.sql.CACHE_KIB`,
`MMAP_BYTES`). There is no client-server backend: it would not make these queries faster, and it
would replace a single portable file with a server to run. Consider one only if several machines
must write the same dataset at the same time.

## Concurrency and crashes

- Writes are SQLite transactions, so an interrupted write leaves the last committed state.
- Several processes may read while one process writes. A `Dataset` object is thread-safe.
- Keep a shared dataset on a local disk of the machine that writes it. SQLite's locking is not
  reliable on network file systems (NFS, SMB), so do not let several machines write one file
  over a network share; read-only access from other machines is fine.
- `"w"` mode refuses to replace a dataset whose write-ahead log (`<path>-wal`) still holds changes; open that dataset once in `"a"` mode to recover them first.
