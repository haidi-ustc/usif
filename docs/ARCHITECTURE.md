# USIF architecture

This is the code-facing description of USIF 0.10. File layouts are specified in
[BINARY_FORMAT.md](BINARY_FORMAT.md) (`.usif` records), [DATASET_FORMAT.md](DATASET_FORMAT.md)
(`.usifc` datasets) and [FORMATS_0_8.md](FORMATS_0_8.md) (files written by USIF 0.8 and earlier).

## 1. Principles

* **One model.** A structure is columns: atomic numbers, Cartesian positions, an optional cell,
  per-atom arrays and structure properties. There are no storage modes or per-atom objects.
* **Exact by default.** Positions are float64, records round-trip bit for bit, and lossy options
  (`precision="f32"`) are explicit.
* **Symmetry is an encoding option.** `symmetry="auto"` stores the asymmetric unit only when it
  reproduces the structure (and its atom order) exactly and makes the record smaller; the model
  never changes shape because of it.
* **Self-describing bytes.** Records carry dtypes, shapes, units and canonical JSON, so decoding
  needs no registry, and hashes are computed from bytes.
* **Borrow robustness.** The dataset is SQLite (transactions, WAL, crash safety, indexes) rather
  than a custom container.
* **Optional libraries stay optional.** The core needs NumPy and spglib; matsimpy, ASE, pymatgen,
  zstandard and the Materials Project client are imported only when used.

## 2. Packages

```text
usif/
  __init__.py      public API: Structure, Cell, read/write/convert, encode/decode, Dataset, Q, errors
  version.py       package and release metadata, FORMAT_VERSION (7), DATASET_SCHEMA_VERSION (1)
  errors.py        USIFError -> ValidationError, FormatError (ChecksumError, UnsupportedVersionError),
                   DatasetError, MissingDependencyError
  elements.py      element table; formula.py: formulas; units.py: unit spelling; fileio.py: atomic writes

  model/           what a structure is
    cell.py        Cell: immutable lattice + pbc, fractional <-> Cartesian
    properties.py  PropertySpec, Schema (DEFAULT_SCHEMA), PropertyMap, JSON normalisation
    structure.py   Structure

  symmetry/        spglib analysis, lossless reduction, expansion
    spacegroup.py  analysis, Hall settings, operations in the stored basis, orbits
    reduce.py      Structure -> SymmetricForm | None
    expand.py      SymmetricForm -> numbers, fractional positions (atom order restored)
    tables.py      frozen format-5 tables (never edit)

  codec/           one structure <-> bytes (current formats)
    wire.py        bounds-checked ByteReader / ByteWriter
    compression.py codec registry: none, zlib, lzma, zstd (optional)
    columns.py     typed column blocks (ARRS, PROP)
    record.py      format-7 records, RecordInfo, identity hashes
    jsondoc.py     JSON document usif.structure.json.v2

  dataset/         many records (.usifc, SQLite)
    sql.py         schema, application id, connection setup
    dataset.py     Dataset, Entry, CheckReport
    query.py       Q -> parameterised SQL

  upgrade/         frozen readers for USIF 0.8 files
    format6.py     .usif formats 5 and 6 -> Structure
    container_v2.py  .usifc version 2 -> entries and record bytes

  backends/        other libraries
    base.py        Backend / FileBackend protocols, registry, entry points
    matsimpy.py, ase.py, pymatgen.py

  io.py            read / read_all / write / write_all / convert

  agent/           local-dataset import and the LLM data agent (CLI-first)
    config.py      LLMConfig: OpenAI-compatible endpoint, DeepSeek by default; key from the environment
    llm.py         ChatClient: /chat/completions with tool calling (standard library HTTP)
    discover.py    scan(): calculations and structure files -> Candidates with provenance
    plan.py        Plan / Operation (usif.agent.plan.v1), apply_plan(): the only write path
    tools.py       Toolbox: read-only dataset and file tools, propose_* tools
    session.py     Session: the model <-> tools loop

  cli/             the usif command (Typer)
    root.py        app, file commands (version, inspect, convert, validate, upgrade), main()
    dataset.py     usif dataset ... (add, list, export, compact, import)
    agent.py       usif agent ... (ask, chat, show, apply, plans, config)
    plans.py       review(): show a plan, apply it only on approval, keep or journal it
    common.py      shared options, JSON/summary output, one-line error messages
```

## 3. Layering

| Layer | Owns | May import inside `usif` |
|---|---|---|
| basics (`version`, `errors`, `elements`, `formula`, `units`, `fileio`) | domain basics | basics |
| `model` | the data model and its invariants | basics |
| `symmetry` | reduction and expansion | basics, model |
| `codec` | current byte formats, identity hashes | basics, model, symmetry |
| `upgrade` | reading 0.8 files (frozen) | basics, model, symmetry, `codec.wire` |
| `dataset` | storage, indexing, queries | basics, model, codec, upgrade |
| `backends` | mapping other libraries' objects | basics, model |
| `io` | single-structure I/O dispatch | basics, model, codec, upgrade, backends |
| `agent` | import, change plans, the LLM agent | basics, model, dataset, io |
| `cli` | the command line | everything above |

`tests/unit/architecture/test_architecture.py` enforces the table with an AST scan of every import,
including imports inside functions. It also checks that optional libraries are never imported at
module level, that the frozen symmetry tables are unchanged, and that the source avoids wording
the project has retired.

```text
basics <- model <- symmetry <- codec <- upgrade
                        ^        ^         ^
                        |        +- dataset+
          backends -----+
              ^
io (codec, upgrade, backends) <- cli (also dataset)
```

## 4. Data flow

* `usif.read(path)`: `.usif` -> `codec.record` (or `upgrade.format6` for format 5/6);
  `.json`/`.usif.json` -> `codec.jsondoc`; anything else -> the first installed backend that reads
  it (matsimpy, ASE, pymatgen, then plugins). Library objects go to the backend whose `accepts()`
  is true.
* `usif.write(structure, path, **options)`: the same dispatch; native files are replaced atomically.
* `Dataset.add(structure, name, group, attrs)`: encode with the dataset's options -> insert the
  record if its hash is new -> derive index rows -> create or update the entry, in one transaction.
* `Dataset.import_v2(path)`: `upgrade.container_v2` -> `upgrade.format6` -> `add`, in one transaction.

## 5. Extension points

| What | How |
|---|---|
| Property definitions | `Schema.register(PropertySpec(...), per_atom=...)` on a copy of `DEFAULT_SCHEMA`, passed to `Structure`, `decode` and `Dataset` |
| Compression codecs | `usif.codec.compression.register(Compressor(id, name, compress, decompress))`; ids are stable bytes |
| Libraries and file formats | `usif.backends.register(backend)` or the `usif.backends` entry-point group |
| Record content | ancillary (lower-case) section tags are skipped by readers that do not know them |

Deliberately absent: a registry of record sections (user data goes in typed columns), pluggable
dataset engines (the SQLite schema *is* the format; measured at 200k entries, every query takes
under about 200 ms, see [datasets](guide/datasets.md#size-and-speed)), and unit conversion (units
are labels).

## 6. Hashes

| Hash | Computed from | Used for |
|---|---|---|
| `record_hash` | BLAKE2b-256 of the raw record payload | record identity, dataset deduplication |
| `geometry_hash` | BLAKE2b-256 of the geometry sections | finding the same geometry with other properties |
| record digest | BLAKE2b-64 of the stored payload, in the header | corruption detection before decompression |

## 7. Security and robustness

* Every byte read is bounds-checked; sizes are validated before allocation; decompression output
  is capped at the declared size; JSON is parsed with recursion errors caught.
* Records are validated through the same model checks as user input.
* Dataset queries bind every value and name as SQL parameters.
* Archive extraction (Materials Project) rejects path traversal and oversized members.
* The agent cannot write: its tools open the dataset read-only and read files only below the
  `--allow` directories; `propose_*` tools build a `Plan`, and only `apply_plan` writes, after a
  person approves. `apply_plan` re-checks source SHA-256s and target entries and runs in one
  transaction. The API key is read from the environment by the HTTP client alone and is redacted
  from error text.
