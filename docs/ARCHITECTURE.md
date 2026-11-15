# USIF Architecture

This document describes the current USIF 0.8.0 architecture. It is intentionally code-facing: module names, public entry points, file-format boundaries, and dependency directions are aligned with the repository source tree.

## 1. System profile

USIF is a Python 3.10+ library for atomistic structure interchange. It provides:

- a pure `USIFStructure` model for crystals and molecules;
- `.usif` single-record binary encoding through `USIF`;
- `.usifc` multi-record containers through `StructureContainer`;
- structure-level and atom-level properties with an injectable registry;
- symmetry analysis, reduction and expansion with spglib (no structure library in the core);
- a backend-neutral array layer plus optional matsimpy, pymatgen and ASE adapters;
- application services for import/export/save/load/optimization;
- optional Materials Project integration and compression benchmarks;
- an official `usif.cli` command-line interface for version, inspect, convert, validate, and container workflows.

Core runtime dependencies are declared in `pyproject.toml`: `numpy`, `spglib`, `typer`, and `tomli` for Python 3.10. The core imports no structure library: matsimpy, pymatgen and ASE are optional extras (`usif[matsimpy]`, `usif[pymatgen]`, `usif[ase]`), loaded only when a conversion to or from their objects or files is requested. Further extras provide Materials Project (`mp`, which also brings `monty`), benchmark, and development tooling. Interop modules are type-checked; external-library imports are tolerated through mypy's missing-import policy rather than hiding USIF adapter code behind `ignore_errors`.

## 2. Package layout

```text
usif/
  constants.py                         # enums and low-level binary constants
  encoder.py                           # public .usif codec facade
  exceptions.py                        # domain exceptions
  units.py                             # unit constants and conversions
  version.py                           # reads project/release metadata from pyproject.toml
  cli.py                               # official Typer-based command-line interface

  structures/
    structure.py                       # pure USIFStructure model
    sites.py                           # WyckoffSite, PointGroupSite, AtomSite
    metadata.py                        # symmetry metadata keys and model object

  properties/
    definitions.py                     # PropertyDefinition
    registry.py                        # PropertyRegistry, DEFAULT_REGISTRY, create_default_registry
    serializer.py                      # thin public PropertySerializer facade
    serializers/                       # focused binary/JSON serializer implementation modules
      scalar.py / vector.py / tensor.py
      json_value.py / numpy_value.py
      validation.py / size.py / dispatch.py
    structure.py                       # StructureProperties
    atomic.py                          # AtomicProperties

  format/
    compression.py                     # NONE/GZIP helpers
    hashing.py                         # geometry, record, payload hashes
    binary/
      header.py                        # 64-byte .usif header (format 6; format 5 still decoded)
      reader.py / writer.py            # bounds-checked primitive I/O
      structure_codec.py               # uncompressed .usif payload body
      property_codec.py                # binary property-section codec
      limits.py                        # defensive decode limits
      integrity.py                     # geometry-hash validation

  storage/
    container.py                       # public .usifc facade and orchestration
    record_store.py                    # file handles, mmap, chunk allocation/read/write
    index_store.py                     # index block read/write, CRC, commit marker, scan recovery
    index_persistence.py               # primary and persisted-secondary index payloads
    indexes.py                         # in-memory primary and secondary indexes
    attributes.py                      # JSON-typed container attribute codec
    groups.py / group_ops.py           # HDF5-like group model and operations
    cache.py                           # decoded-structure LRU cache
    query.py                           # query candidate selection
    prefetch.py                        # batch/prefetch helpers
    recovery.py                        # record scanning recovery helpers
    validation.py                      # container.validate() service

  elements.py                          # element table (Z, symbol, electronegativity)
  formula.py                           # reduced_formula(): core-owned reduced formula
  fileio.py                            # atomic file replacement (temp file + fsync + rename)

  interop/
    common/
      arrays.py                        # AtomsData, build_structure(), structure_to_arrays()
      importing.py                     # import_atoms(): shared per-atom overrides + SymmetryPolicy
      type_guards.py                   # import-free runtime guards for supported objects
    matsimpy/adapter.py                # matsimpy Crystal/Molecule <-> USIF
    pymatgen/adapter.py                # pymatgen Structure/Molecule <-> USIF
    ase/adapter.py                     # ase.Atoms <-> USIF (no pymatgen)

  symmetry/
    policies.py                        # SymmetryPolicy, apply_symmetry_policy()
    spacegroup.py                      # spglib analysis, Hall-number settings, orbit expansion
    tables.py                          # frozen format-5 space-group -> Hall and point-group tables
    reduce.py                          # SymmetryReducer (lossless-gated), lazily imported
    expand.py                          # expand_structure(): SYMMETRIC -> FULL_ATOMIC

  services/
    convert.py                         # import_structure/export_structure, foreign file I/O
    io.py                              # .usif and official JSON save/load dispatch
    json_io.py                         # official USIF JSON schema helpers
    optimizer.py                       # USIFOptimizer/optimize_structure

  benchmarks/
    compression.py                     # USIFBenchmark/benchmark_compression

  integrations/materials_project/
    client.py                          # lazy mp-api client wrapper
    query.py                           # query group definitions and kwargs
    downloader.py                      # high-level dataset download orchestration
    mapper.py                          # MP document -> USIFStructure (no pymatgen needed)
    archive.py                         # zip creation and safe extraction
    loader.py                          # load local fixture/downloaded groups
    dependencies.py                    # lazy optional imports
```

The public surface is limited to documented package entry points. Internal implementation modules remain importable only through their canonical packages; removed package paths are not part of the API.

## 3. Dependency direction

The intended dependency direction is:

```text
structures  <-  properties
    ^              ^
    |              |
format/binary ----+
    ^
    |
storage

structures <- symmetry (spglib) <- interop/common <- interop/<backend> <- services
structures <- symmetry <- services/optimizer
structures <- integrations/materials_project
structures <- benchmarks
```

Important boundaries:

1. USIFStructure is a pure model. `USIFStructure` It does not import `usif.services`, `usif.interop`, `usif.storage`, or `usif.encoder`.
2. `USIF` is the `.usif` codec facade. It delegates header, payload, property, compression, and integrity work to `usif.format` modules.
3. `StructureContainer` stores encoded `.usif` records. It depends on `USIF`, but the `.usif` codec does not depend on storage.
4. Interop adapters depend on model/properties/symmetry, not on storage. Every adapter converts through the backend-neutral array layer (`usif.interop.common`), so per-atom property mapping, `SymmetryPolicy` handling and validation exist once.
5. Nothing outside `usif/interop/<backend>/` and the service-level file readers imports matsimpy, pymatgen or ASE; `import usif` loads none of them.
6. Services are application-boundary helpers; they may call codec, interop, and model modules.
7. Materials Project and benchmarks live outside `services` because they are optional integrations/tooling.

## 4. Public API boundaries

### Core model

```python
from usif import USIFStructure, StructureType, StorageMode
from usif import WyckoffSite, PointGroupSite, AtomSite
from usif import StructureProperties, AtomicProperties
```

`USIFStructure` keeps structure data, validation, `as_dict()`, `from_dict()`, `copy()`, display helpers, and equality behavior. It does not expose `from_source()`, `from_pymatgen()`, `to()`, `save()`, or `load()`.

### Binary codec

```python
from usif import USIF, CompressionType
```

`USIF.encode()` returns complete `.usif` bytes. `USIF.decode()` returns `(USIFStructure, geometry_hash)`. `USIF.save()` and `USIF.load()` remain codec-level file helpers; application code can also use `usif.services.save_structure()` and `load_structure()` for `.usif`, `.json`, and `.usif.json` files.

### Services

```python
from usif.services import import_structure, export_structure
from usif.services import import_matsimpy, import_pymatgen, read_foreign_file
from usif.services import save_structure, load_structure
from usif.services import optimize_structure, USIFOptimizer
```

Services are the canonical application boundary for object import/export and file save/load. They replace model-level convenience methods. `import_structure()` accepts a path or a matsimpy, pymatgen or ASE object and dispatches on the object type; `export_structure(s, fmt=...)` returns a `"matsimpy"`, `"pymatgen"`, `"ase"` or backend-free `"arrays"` object. Non-USIF files (CIF, POSCAR, XYZ, ...) are read and written with the first installed backend, tried in the order matsimpy, ASE, pymatgen.

### Official USIF JSON

USIF 0.8.0 supports an official USIF JSON document at the service boundary. The implementation lives in `usif.services.json_io` and uses the schema marker `usif.structure.json.v1`. The JSON service serializes the pure model dictionary into interoperable JSON and restores it through `USIFStructure.from_dict()`.

Supported JSON path suffixes are `.json` and `.usif.json`. Unsupported non-`.usif` extensions are rejected by `save_structure()` and `load_structure()` so format selection remains explicit. JSON serialization accepts JSON-compatible custom values and normalized NumPy arrays/scalars; unsupported objects and non-finite floats raise `StorageError`.

### Interop

```python
from usif.interop.common import AtomsData, build_structure, structure_to_arrays
from usif.interop.matsimpy import MatsimpyImporter, MatsimpyExporter
from usif.interop.pymatgen import PymatgenImporter, PymatgenExporter
from usif.interop.ase import ASEImporter, ASEExporter
from usif.symmetry import SymmetryPolicy
```

`usif.interop.common` is the backend-neutral array layer. `build_structure()` turns atomic numbers, positions, an optional lattice and property arrays into a FULL_ATOMIC `USIFStructure` (a missing or degenerate lattice means a molecule); `structure_to_arrays()` returns `AtomsData` (Cartesian positions, lattice, pbc, per-atom arrays, energy, stress, custom values), expanding SYMMETRIC records first. `import_atoms()` applies caller overrides (forces, charges, magmoms, energy, stress) and the `SymmetryPolicy`.

Each backend adapter only maps its objects to and from `AtomsData`:

- matsimpy: `Crystal`/`Molecule`; per-site dicts and `metadata` (energy, stress, custom values).
- pymatgen: `Structure`/`Molecule`; oxidation states, molecule charge and spin multiplicity are kept as custom values and restored on export; disordered structures are rejected.
- ASE: `Atoms`; calculator energy/forces/stress, charges, magnetic moments, velocities and per-atom arrays. Stress is converted from eV/Å³ to GPa and velocities to Å/fs. The ASE adapter does not depend on pymatgen.

Runtime type guards (`is_matsimpy_object()`, `is_pymatgen_structure()`, `is_pymatgen_molecule()`, `is_ase_atoms()`) check the class lineage by module and name, so they never import the optional library.

### Symmetry

SYMMETRIC crystals are produced and expanded with spglib. A format-6 record stores the spglib Hall number and, when it is not the default, the transformation `(P, p)` from the stored cell to the standard setting (`x_std = P x + p`), so expansion reproduces the stored cell and origin exactly. Reduction is attempted at several `symprec` values and is accepted only when re-expansion reproduces every original atom within `SymmetryConstants.LOSSLESS_TOLERANCE` (1e-5 Å, after float32 rounding); otherwise the structure stays FULL_ATOMIC. Molecules are not reduced. Format-5 records, which store only a space-group number, are expanded with a frozen space-group -> Hall table (`usif/symmetry/tables.py`) matching the settings they were written with.

### Storage

```python
from usif.storage import StructureContainer
```

`StructureContainer` is the public `.usifc` facade. Low-level file/chunk/index work is delegated to `RecordStore` and `ContainerIndexStore`.

### Properties

```python
from usif import PropertyDefinition, PropertyRegistry
from usif import DEFAULT_REGISTRY, create_default_registry
```

The registry is instance-based. Use `DEFAULT_REGISTRY` for built-ins and `create_default_registry()` when isolation is needed.

### Optional tooling

```python
from usif.benchmarks import benchmark_compression
from usif.integrations.materials_project import download_mp_data, load_mp_group, convert_mp_to_usif
```

The generic `usif.utils` package is not part of the 6.0 API.

## 5. Main workflows

### Import and save a single structure

```text
matsimpy / pymatgen / ASE object, or a CIF/POSCAR/... file
  -> usif.services.import_structure()
  -> backend adapter -> AtomsData -> import_atoms() -> SymmetryPolicy
  -> USIFStructure
  -> usif.services.save_structure()
  -> USIF.encode()
  -> .usif file
```

### Decode a `.usif` file

```text
.usif bytes/file
  -> USIFHeader.parse()
  -> decompress_data()
  -> StructureBinaryCodec.decode_body()
  -> validate_geometry_hash()
  -> USIFStructure
```

### Store records in a `.usifc` container

```text
USIFStructure
  -> StructureContainer.add()
  -> USIF.encode()
  -> record_hash + geometry_hash
  -> RecordStore.allocate()/write_record()
  -> ContainerIndexes update
  -> flush()/autocommit/close(): serialize index payload
  -> ContainerIndexStore.write_index_block()
  -> header index_offset update
```

### Open and query a `.usifc` container

```text
StructureContainer(mode="r")
  -> ContainerIndexStore.read_container_header()
  -> ContainerIndexStore.read_index_block_at(header.index_offset)
  -> IndexPersistenceMixin._deserialize_indexes_from_payload()
  -> load persisted geometry/formula/property secondary indexes
  -> QueryEngine.candidate_hashes()
  -> StructureContainer.get()
  -> USIF.decode() only for matching records
```

If the header points to an invalid index generation, `ContainerIndexStore.find_latest_valid_index_offset()` scans in bounded chunks for the newest valid committed index block.

USIF 0.8.0 persists secondary indexes (`geometry_index`, `formula_index`, and `property_index`) in the checksummed container index generation. This keeps read-only open cost bounded to header + index payload reads, instead of decoding every stored record before the first query. Older index payloads without the secondary section can still be rebuilt from records by `IndexPersistenceMixin._build_secondary_indexes()`.

`StructureContainer.validate()` is explicit about validation cost: `level="index"` checks metadata/index references, `level="records"` also reads record byte ranges and USIF headers, and `level="full"` decodes every structure and verifies record hashes.

## 6. Hash semantics

USIF deliberately separates three identities:

| Hash | Owner | Purpose |
|---|---|---|
| geometry hash | `calculate_geometry_hash()` / `USIF.get_geometry_hash()` | geometry-only identity used for grouping and integrity validation |
| record hash | `calculate_record_hash()` / `USIF.get_record_hash()` | logical record identity including formula and properties, used for container deduplication |
| payload digest | `calculate_payload_digest()` | raw byte digest for payload-oriented checks |

The record hash is computed on the canonical (encode -> decode) form of a structure, so it is stable across save/load. The geometry hash includes the symmetry setting only when it is not the default one, so format-5 geometry hashes are unchanged.

`.usif` headers store the geometry hash. `.usifc` primary records are keyed by record hash, while `geometry_index` maps one geometry hash to one or more record hashes.

## 7. Release/version metadata

Packaging version and the date-based unique release record are declared in `pyproject.toml`:

```toml
[project]
version = "0.8.0"

[tool.usif.release]
date = "2026-11-15"
sequence = 17
record = "20261115.017"
id = "usif-20261115-017"
```

`usif.version` reads these values from `pyproject.toml` in a source checkout and falls back to baked constants or installed package metadata in wheel installs. `FORMAT_VERSION = 6` is the `.usif` binary record format version and changes only when the binary record layout changes.

USIF uses `scripts/check_release_metadata.py` as the release governance gate. The checker validates `pyproject.toml`, baked `usif.version` fallback constants, CI wheel-smoke expectations, and the latest changelog entry before packaging. `docs/FORMAT_VERSIONING.md` defines package, release-record, `.usif`, and `.usifc` version boundaries; `docs/API_STABILITY.md` defines the stable 0.8.x public API surface.

## 8. Testing and release boundaries

Tests are layered by directory:

```text
tests/unit/          fast unit and architecture-boundary tests
tests/integration/   interop, service, and Materials Project fixture tests
tests/reliability/   corruption, integrity, concurrency, recovery tests
tests/examples/      executable example smoke tests
tests/fixtures/      deterministic local data
```

The CI workflow runs formatting (`black --check`, `isort --check-only`), type checks (`mypy usif`), security checks (`bandit -q -r usif`, `pip_audit`), unit tests, integration/reliability/example tests, source/wheel builds, and clean wheel installation smoke tests.


## 6.2 property-management note

The property layer provides shape-aware property management for structure and atomic scopes. `StructureProperties`, `AtomicProperties`, and pure-model helpers on `USIFStructure` normalize built-in scalar/vector/tensor values and JSON-compatible custom values before they enter binary, JSON, or container persistence.


## Documentation site

USIF ships a plain-Markdown documentation site under `docs/site/`. The site is organized around concepts, tutorials, cookbook recipes, and the public API map. It complements the normative engineering documents (`ARCHITECTURE.md`, `BINARY_FORMAT.md`, `CONTAINER_FORMAT.md`, and `PROPERTY_SYSTEM.md`) without replacing them.


## 13. Command-line interface

USIF 0.8.0 exposes an official `usif` console script through `[project.scripts]` in `pyproject.toml`:

```toml
[project.scripts]
usif = "usif.cli:main"
```

The CLI delegates to stable application services and storage facades rather than duplicating codec logic. The supported command groups are:

- `usif version` for package, release-record, and binary format metadata;
- `usif inspect` for `.usif`, `.json`, `.usif.json`, and `.usifc` summaries;
- `usif convert` for official `.usif` <-> JSON conversion;
- `usif validate` for structure or container validation;
- `usif container stats`, `list`, and `query` for `.usifc` introspection and indexed searches.

The CLI is an application boundary. The pure `USIFStructure` model and binary codec do not import or depend on it.
