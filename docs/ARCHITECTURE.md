# USIF Architecture

This document describes the current USIF 6.8.0 architecture. It is intentionally code-facing: module names, public entry points, file-format boundaries, and dependency directions are aligned with the repository source tree.

## 1. System profile

USIF is a Python 3.10+ library for atomistic structure interchange. It provides:

- a pure `USIFStructure` model for crystals and molecules;
- `.usif` single-record binary encoding through `USIF`;
- `.usifc` multi-record containers through `StructureContainer`;
- structure-level and atom-level properties with an injectable registry;
- explicit pymatgen and ASE adapters;
- application services for import/export/save/load/optimization;
- optional Materials Project integration and compression benchmarks.

Core runtime dependencies are declared in `pyproject.toml`: `numpy`, `pymatgen`, `monty`, and `tomli` for Python 3.10. Optional extras provide ASE, Materials Project, benchmark, and development tooling. Interop modules are type-checked in 6.8.0; external-library imports are tolerated through mypy's missing-import policy rather than hiding USIF adapter code behind `ignore_errors`.

## 2. Package layout

```text
usif/
  constants.py                         # enums and low-level binary constants
  encoder.py                           # public .usif codec facade
  exceptions.py                        # domain exceptions
  units.py                             # unit constants and conversions
  version.py                           # reads project/release metadata from pyproject.toml

  structures/
    structure.py                       # pure USIFStructure model
    sites.py                           # WyckoffSite, PointGroupSite, AtomSite
    metadata.py                        # symmetry metadata keys and object

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
    properties.py                      # binary property-section codec
    binary/
      header.py                        # 64-byte .usif v5 header
      reader.py / writer.py            # bounds-checked primitive I/O
      structure_codec.py               # uncompressed .usif payload body
      property_codec.py                # property codec import boundary
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

  interop/
    common/
      protocols.py                    # adapter Protocol contracts for pymatgen/ASE surfaces
      type_guards.py                  # runtime TypeGuard helpers for supported objects
    pymatgen/
      importer.py                      # small dispatch facade
      crystal_importer.py              # pymatgen Structure -> USIF crystal
      molecule_importer.py             # pymatgen Molecule -> USIF molecule
      exporter.py                      # small dispatch facade
      crystal_exporter.py              # USIF crystal -> pymatgen Structure
      molecule_exporter.py             # USIF molecule -> pymatgen Molecule
      property_extractor.py            # property extraction helpers
    ase/
      importer.py / exporter.py        # ASE adapters through canonical pymatgen adapters

  symmetry/
    policies.py                        # SymmetryPolicy
    analysis.py                        # pymatgen-backed Wyckoff/point-group extraction
    equivalence.py                     # losslessness checks and orbit expansion
    reduce.py                          # SymmetryReducer service, lazily imported by package __getattr__
    expand.py / metadata.py            # public helper aliases

  services/
    convert.py                         # import_structure/export_structure/import_pymatgen
    io.py                              # .usif and official JSON save/load dispatch
    json_io.py                         # official USIF JSON schema helpers
    optimizer.py                       # USIFOptimizer/optimize_structure

  benchmarks/
    compression.py                     # USIFBenchmark/benchmark_compression

  integrations/materials_project/
    client.py                          # lazy mp-api client wrapper
    query.py                           # query group definitions and kwargs
    downloader.py                      # high-level dataset download orchestration
    mapper.py                          # MP document -> USIFStructure
    archive.py                         # zip creation and safe extraction
    loader.py                          # load local fixture/downloaded groups
    dependencies.py                    # lazy optional imports
```

Removed API packages intentionally remain absent in 6.1.0: `usif.converter`, `usif.container`, `usif.io`, `usif.utils`, `usif.interop.converter_core`, `usif.interop.symmetry`, `usif.structures.io`, and `usif.structures.source`.

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

structures <- interop <- services
structures <- symmetry <- services/optimizer
structures <- integrations/materials_project
structures <- benchmarks
```

Important boundaries:

1. USIFStructure is a pure model. `USIFStructure` It does not import `usif.services`, `usif.interop`, `usif.storage`, or `usif.encoder`.
2. `USIF` is the `.usif` codec facade. It delegates header, payload, property, compression, and integrity work to `usif.format` modules.
3. `StructureContainer` stores encoded `.usif` records. It depends on `USIF`, but the `.usif` codec does not depend on storage.
4. Interop adapters depend on model/properties/symmetry, not on storage.
5. Services are application-boundary helpers; they may call codec, interop, and model modules.
6. Materials Project and benchmarks live outside `services` because they are optional integrations/tooling.

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
from usif.services import import_structure, import_pymatgen, export_structure
from usif.services import save_structure, load_structure
from usif.services import optimize_structure, USIFOptimizer
```

Services are the canonical application boundary for object import/export and file save/load. They replace model-level convenience methods.

### Official USIF JSON

USIF 6.8.0 supports an official USIF JSON document at the service boundary. The implementation lives in `usif.services.json_io` and uses the schema marker `usif.structure.json.v1`. The JSON service serializes the pure model dictionary into interoperable JSON and restores it through `USIFStructure.from_dict()`.

Supported JSON path suffixes are `.json` and `.usif.json`. Unsupported non-`.usif` extensions are rejected by `save_structure()` and `load_structure()` so format selection remains explicit. JSON serialization accepts JSON-compatible custom values and normalized NumPy arrays/scalars; unsupported objects and non-finite floats raise `StorageError`.

### Interop

```python
from usif.interop.pymatgen import (
    PymatgenImporter, PymatgenExporter,
    CrystalImporter, CrystalExporter,
    MoleculeImporter, MoleculeExporter,
    SymmetryPolicy,
)
from usif.interop.ase import ASEImporter, ASEExporter
```

`PymatgenImporter` and `PymatgenExporter` are dispatch facades. Crystal/molecule adapters own the specific conversion paths. The interop common protocols (`PymatgenStructureLike`, `PymatgenMoleculeLike`, and `ASEAtomsLike`) document the minimal external-library surfaces USIF consumes, while runtime type guards (`is_pymatgen_structure()`, `is_pymatgen_molecule()`, and `is_ase_atoms()`) keep adapter errors explicit. ASE adapter depends on pymatgen because ASE import/export intentionally routes through pymatgen's `AseAtomsAdaptor` and the canonical pymatgen adapters.

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
pymatgen Structure/Molecule or ASE Atoms
  -> usif.services.import_structure()
  -> interop adapter
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
  -> close(): serialize index payload
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

USIF 6.8.0 persists secondary indexes (`geometry_index`, `formula_index`, and `property_index`) in the checksummed container index generation. This keeps read-only open cost bounded to header + index payload reads, instead of decoding every stored record before the first query. Older index payloads without the secondary section can still be rebuilt from records by `IndexPersistenceMixin._build_secondary_indexes()`.

`StructureContainer.validate()` is explicit about validation cost: `level="index"` checks metadata/index references, `level="records"` also reads record byte ranges and USIF headers, and `level="full"` decodes every structure and verifies record hashes.

## 6. Hash semantics

USIF deliberately separates three identities:

| Hash | Owner | Purpose |
|---|---|---|
| geometry hash | `calculate_geometry_hash()` / `USIF.get_geometry_hash()` | geometry-only identity used for grouping and integrity validation |
| record hash | `calculate_record_hash()` / `USIF.get_record_hash()` | logical record identity including formula and properties, used for container deduplication |
| payload digest | `calculate_payload_digest()` | raw byte digest for payload-oriented checks |

`.usif` headers store the geometry hash. `.usifc` primary records are keyed by record hash, while `geometry_index` maps one geometry hash to one or more record hashes.

## 7. Release/version metadata

Packaging version and the date-based unique release record are declared in `pyproject.toml`:

```toml
[project]
version = "6.8.0"

[tool.usif.release]
date = "2026-06-05"
sequence = 12
record = "20260605.013"
id = "usif-20260605-013"
```

`usif.version` reads these values from `pyproject.toml` in a source checkout and falls back to baked constants or installed package metadata in wheel installs. `FORMAT_VERSION = 5` is the `.usif` binary record format version and changes only when the binary record layout changes.

USIF 6.8.0 adds `scripts/check_release_metadata.py` as the release governance gate. The checker validates `pyproject.toml`, baked `usif.version` fallback constants, CI wheel-smoke expectations, and the latest changelog entry before packaging. `docs/FORMAT_VERSIONING.md` defines package, release-record, `.usif`, and `.usifc` version boundaries; `docs/API_STABILITY.md` defines the stable 6.x public API surface.

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
