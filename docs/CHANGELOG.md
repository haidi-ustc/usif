# Changelog

## 0.9.0

Release record `20261116.018`, release ID `usif-20261116-018`. This release redesigns the library and
its file formats. It is not API-compatible with 0.8, but it reads every file 0.8 wrote.

### Model

- `usif.Structure` replaces `USIFStructure`. A structure is columns: `numbers`, Cartesian
  `positions` (float64), an optional immutable `Cell` with `pbc`, per-atom `arrays` and structure
  `properties`. Both are `PropertyMap`s with dtypes, shapes and units.
- There are no storage modes. Symmetry is an encoding option (`symmetry="auto"`), not a property of
  the structure, so any structure can carry per-atom data.
- `Schema` / `PropertySpec` / `DEFAULT_SCHEMA` replace `PropertyRegistry`, `AtomicProperties` and
  `StructureProperties`. Unknown names are accepted as typed or JSON columns.
- Units are labels: `usif.units` normalises their spelling (NFC, `µ`/`μ`, `Ang`, `bohr`, ...) and
  never converts stored values. `usif.units.convert` (CODATA 2018; 1 eV/Å³ = 160.2176634 GPa) is
  used by the backends to export built-in quantities in each library's units; an unconvertible
  unit raises `ValidationError`.
- Built-in properties gained `free_energy` (eV) and `dipole` (e·Å). `stress` is documented as
  Cauchy stress, positive tensile (ASE sign). `magmom` must be (N,) or (N, 3);
  `spin_multiplicity` must be at least 1; integer properties reject values out of range instead
  of wrapping.

### Formats

- `.usif` record format 7 (`FORMAT_VERSION = 7`, [BINARY_FORMAT.md](BINARY_FORMAT.md)): a 40-byte
  header with a BLAKE2b digest of the stored payload, tagged sections (`ATOM`, `CELL`, `POSN`/`SYMM`,
  `ARRS`, `PROP`, plus skippable ancillary sections), self-describing typed columns, and
  deterministic encoding. Options: compression `none`/`zlib`/`lzma`/`zstd` (`usif[zstd]`),
  precision `f64`/`f32`, symmetry `off`/`auto`.
- Symmetric records keep the original atom order and are used only when lossless (1e-5 Å) and
  smaller.
- Every field has one wire dtype and decoding accepts only canonical bytes, so a decoded record
  re-encodes to the same bytes.
- `record_hash` and `geometry_hash` are BLAKE2b-256 of the payload and of its geometry sections.
- JSON documents use schema `usif.structure.json.v2`.
- `.usifc` is now an SQLite dataset ([DATASET_FORMAT.md](DATASET_FORMAT.md)): deduplicated
  records, groups, JSON attributes, indexed queries with `Q`, transactions, concurrent readers and
  integrity checks (`DATASET_SCHEMA_VERSION = 1`).
- Files written by 0.8 and earlier ([FORMATS_0_8.md](FORMATS_0_8.md)) are read by frozen readers in
  `usif.upgrade`: format-5/6 records through `usif.read()`, version-2 containers through
  `Dataset.import_v2()` or `usif upgrade`.

### API and tools

- `usif.read`, `read_all`, `write`, `write_all` and `convert` replace the `services` functions.
- `usif.backends` replaces `usif.interop`: matsimpy, ASE and pymatgen backends behind one
  `Backend` protocol, plus third-party backends from the `usif.backends` entry-point group.
- The CLI has `version`, `inspect`, `convert`, `validate`, `upgrade` and `dataset
  add/list/export/compact`.
- Benchmarks (`python -m scripts.benchmark`) and the Materials Project tooling
  (`python -m scripts.materials_project download|build`) are development scripts, no longer part
  of the package. The Materials Project `energy` is now the raw DFT total
  (`uncorrected_energy_per_atom * natoms`), not the MP2020-corrected value.
- An architecture test enforces the package layering.
- Dataset property and element conditions are answered from their indexes (`IN` subqueries);
  `Q.prop(name).between(low, high)` is a single index range (it was a quadratic plan).
- `usif.RELEASE_RECORD`, `RELEASE_ID` and `RELEASE_DATE` are exported at the top level.
- Documentation: one user guide (`docs/guide/`, indexed by `docs/README.md`) replaces
  `docs/site/`; `PROPERTY_SYSTEM.md` moved into the guide, `TESTING.md` into `CONTRIBUTING.md`
  and `VERSIONING.md` into `RELEASE.md`.
- `click` is no longer a dependency.

### Migration from 0.8

| 0.8 | 0.9 |
|---|---|
| `USIFStructure(...)`, `StorageMode` | `Structure(numbers, positions, cell, arrays=..., properties=...)` |
| `structure.atom_sites[i].properties.force` | `structure.arrays["force"][i]` |
| `structure.structure_properties.energy` | `structure.properties["energy"]` |
| `import_structure(obj)` / `export_structure(s, "ase")` | `usif.convert(obj)` / `usif.convert(s, "ase")` |
| `save_structure(s, path)` / `load_structure(path)` | `usif.write(s, path)` / `usif.read(path)` |
| `USIF().encode(s)` / `USIF().decode(b)` | `usif.encode(s)` / `usif.decode(b)` |
| `SymmetryPolicy`, `optimize_structure` | `encode(s, symmetry="auto")`, `Dataset(path, symmetry="auto")` |
| `StructureContainer(path).add(s)` | `Dataset(path).add(s, name, group, attrs)` |
| container filters | `dataset.query(Q.formula("NaCl") & (Q.prop("energy") < 0))` |
| old `.usifc` files | `usif upgrade old.usifc new.usifc` |

## 0.8.0

Updated release metadata to the date record `20261115.017` and release ID `usif-20261115-017`.

### Dependencies and backends

- The core no longer depends on pymatgen or monty. Runtime dependencies are `numpy`, `spglib`, `typer` (and `tomli` on Python 3.10); `import usif` loads no structure library.
- matsimpy, pymatgen and ASE are independent optional backends (`usif[matsimpy]`, `usif[pymatgen]`, `usif[ase]`). matsimpy is not on PyPI and must be installed from its source checkout. `monty` moved to the `mp` extra.
- Added the backend-neutral array layer `usif.interop.common` (`AtomsData`, `build_structure()`, `structure_to_arrays()`, `import_atoms()`); every adapter converts through it, so per-atom mapping and `SymmetryPolicy` handling exist once. The same structure imported through matsimpy or pymatgen gives the same record hash.
- Added the matsimpy adapter (`MatsimpyImporter`, `MatsimpyExporter`), `import_matsimpy()`, `read_foreign_file()`, and `export_structure(..., fmt="arrays")`. Non-USIF files are read and written with matsimpy, ASE or pymatgen, in that order.
- The ASE adapter no longer goes through pymatgen.
- The Materials Project mapper parses structure documents natively, without pymatgen.
- The reduced formula, element table and type guards are core-owned and import no optional library.

### Format 6 and symmetry

- `.usif` `FORMAT_VERSION` is now `6`. Symmetric crystals store the spglib Hall number and the setting transformation `(P, p)`, so expansion reproduces the stored cell, origin and supercell exactly. Symmetric site counts and multiplicities are `uint32`, so symmetric records are no longer limited to 255 sites.
- Format-5 records and containers remain readable. Their symmetric crystals are expanded through a frozen space-group -> Hall table, which matches the settings they were written with for all 230 space groups. Golden format-5 fixtures are covered by tests.
- Symmetry reduction uses spglib and is kept only when it is lossless: re-expansion must reproduce every atom within 1e-5 Å after float32 rounding. Previously `force_symmetric` could store a primitive cell, a shifted origin, or a wrong point group (Td/C3v molecules). Molecules are now always stored full-atomic.
- `USIFOptimizer` keeps a symmetric reduction only when its encoding is smaller.
- `USIFStructure` gained `hall_number`, `setting_transformation`, `origin_shift`, `symmetry_setting()`, `has_default_setting()` and `copy()`.

### Fixes

- Site-property magnetic moments (pymatgen, matsimpy, MP documents) are imported, so antiferromagnetic order is no longer erased by symmetry reduction.
- pymatgen oxidation states, molecule charge and spin multiplicity are preserved; disordered structures raise `ValidationError` instead of crashing.
- ASE stress is converted from eV/Å³ to GPa (it was stored 160x too small) and velocities to Å/fs; partial periodic boundary conditions are kept.
- `USIF.save()` and JSON saves encode before writing and replace files atomically, so a failed save no longer truncates an existing file.
- Record hashes are computed on the canonical (encode -> decode) structure and are stable across save/load.
- Custom values that are not JSON-compatible raise an error instead of being stored as `str()`.

### Containers

- Writers take an exclusive lock; a second writer gets `ContainerError`.
- Mode `"w"` writes to a temporary file that replaces the target on close, so an aborted rewrite leaves the original file intact.
- Added `flush()` and `autocommit_every` so the index can be committed without closing; uncommitted data is reported on open.
- Recovery scans to the end of the file instead of stopping at the index offset, and deduplicates by record hash.
- `get()` returns copies, so mutating a result no longer corrupts the decoded-structure cache.
- Index buckets are ordered sets, so adding many records with the same formula or geometry is no longer quadratic.
- Group and attribute validation is stricter; rebinding a name drops its stale attributes.

## 0.7.1

- Renumbered the package version from `7.1.0` to `0.7.1` (pre-1.0 versioning). The code is identical to the 7.1.0 release; earlier changelog headings keep their historical numbers. Future releases bump the minor version (`0.8.0`, `0.9.0`, ...) before any major version.

- Completed the 7.1 cleanup line for runtime code and current documentation.
- Moved the real `PropertyCodec` implementation into `usif.format.binary.property_codec` and removed the forwarding `usif.format.properties` module.
- Removed the `StructureContainer.add_structure()` alias; `StructureContainer.add()` is the single public insertion API.
- Removed the `decode_records` validation flag; container validation now uses only explicit levels: `index`, `records`, and `full`.
- Simplified `StructureContainer.stats()` to one stable schema with nested `cache` and `storage` sections.
- Removed the `usif.symmetry.metadata` forwarding module; symmetry metadata remains canonical under `usif.structures.metadata` and top-level `usif` exports.
- Tightened `.usif` decoding to reject unsupported record format versions instead of attempting best-effort decode.
- Bumped `.usifc` container header version to `2` and require persisted secondary indexes in the current index payload.
- Kept binary `FORMAT_VERSION` at 5 because the `.usif` single-record layout did not change.
- Updated release metadata to the date record `20260605.016` and release ID `usif-20260605-016`.

## 7.0.0

- Promoted USIF to the 7.0 long-term stable architecture line.
- Added the official Typer-powered `usif` command-line interface through the `usif = "usif.cli:main"` console script.
- Added CLI commands for version metadata, structure/container inspection, `.usif` <-> JSON conversion, validation, container statistics, container index listing, and indexed container queries.
- Added focused CLI tests that exercise the Typer entry point directly without requiring optional pymatgen/ASE objects.
- Updated documentation, README, release governance, and the docs site to describe CLI usage and public API boundaries.
- Updated release metadata to the date record `20260605.015` and release ID `usif-20260605-015`.
- Kept binary `FORMAT_VERSION` at 5 because the `.usif` single-record format layout did not change.
- Skipped the 6.9 line and added a productized user documentation site under `docs/site/` with quickstart, concepts, tutorials, cookbook recipes, and a public API map.
- Added documentation-site release guardrails so site pages are packaged, tested, and kept aligned with the current package version and release record.
- Added `examples/10_materials_project_dataset.py` as a clearer Materials Project dataset example with safe `--help` behavior and explicit local dataset conversion guidance.
- Updated README and examples documentation to point users from quick-start snippets to the complete documentation site.

## 6.8.0

- Fixed pymatgen import property extraction to use `StructureProperties` and `AtomicProperties` setters so built-in default units are present before record hashing; full container validation now remains stable after encode/decode round-trips.
- Added lightweight `.usifc` introspection APIs: `list_names()`, `list_formulas()`, `list_properties()`, and `list_groups()`.
- Expanded `StructureContainer.stats()` with compact aliases, formulas, indexed properties, group paths, file size, index size, and compression ratio without decoding records.
- Added enhanced indexed query filters: `has_property`, `property_range=(name, min, max)`, and `custom={dotted.path: value}`.
- Extended `ContainerValidationResult` with `checked_records` and `elapsed_seconds` for validation reporting.
- Added container introspection, enhanced query, and import-unit hash-stability regression tests.
- Updated release metadata to the date record `20260605.013` and release ID `usif-20260605-013`.
- Kept binary `FORMAT_VERSION` at 5 because the `.usif` single-record format layout did not change.

## 6.7.0

- Added canonical unit metadata support to structure-level and atom-level property setters.
- Added Unicode/ASCII unit alias normalization so spellings such as `Å²`, `Å^2`, `Ang^2`, and `angstrom^2` normalize to `Å^2`; `eV/Ang` normalizes to `eV/Å`.
- Added `PropertyValue` envelopes for custom scalar, vector, tensor, and metadata-rich properties with optional `units`, `description`, and `metadata` fields.
- Built-in properties now keep default unit metadata (`energy=eV`, `stress=GPa`, `volume=Å^3`, `force=eV/Å`, `charge=e`, etc.) while preserving the existing bare-value getter behavior.
- Unit metadata round-trips through model JSON dictionaries, `.usif` binary records, official `.json` / `.usif.json` documents, and `.usifc` container records.
- Added `examples/08_property_units.py` and focused unit-alias/property-unit regression tests.
- Updated release metadata to the date record `20260605.012` and release ID `usif-20260605-012`.
- Kept binary `FORMAT_VERSION` at 5 because the `.usif` single-record format layout did not change.

## 6.5.2

- Fixed release governance packaging by making `scripts` an installable package so `scripts.check_release_metadata` can be imported consistently from source and installed test runs.
- Ensured CI contains the exact `python scripts/check_release_metadata.py` release-guard command expected by engineering workflow tests.
- Updated release metadata to the date record `20260605.010` and release ID `usif-20260605-010`.
- Kept binary `FORMAT_VERSION` at 5 because the `.usif` single-record format did not change.

## 6.5.1

- Fixed the ASE interop contract test to construct a real ASE `Atoms` object with symbols and positions instead of using the invalid `Atoms(2)` form.
- Added `scripts/check_release_metadata.py` to validate pyproject-driven package version, date-based release record, baked wheel fallback constants, CI wheel-smoke expectations, and the latest changelog entry.
- Added `docs/FORMAT_VERSIONING.md` to separate package versioning, dated release records, `.usif` binary record format versioning, and `.usifc` container format governance.
- Added `docs/API_STABILITY.md` to define stable public APIs, internal APIs, experimental APIs, and 6.x breaking-change expectations.
- Updated CI and release documentation to run the release metadata checker and to support generating `release-checks.txt` next to published artifacts.
- Updated release metadata to the date record `20260605.009` and release ID `usif-20260605-009`.
- Kept binary `FORMAT_VERSION` at 5 because the `.usif` single-record format did not change.

## 6.4.0

- Added `usif.interop.common` protocols and runtime type guards for pymatgen/ASE adapter contracts.
- Removed the `usif.interop.*` mypy `ignore_errors` override so adapter code is no longer hidden from type checks.
- Made ASE dependency semantics explicit: ASE import/export routes through pymatgen's `AseAtomsAdaptor` and canonical pymatgen adapters.
- Tightened pymatgen property extraction by validating per-site property lengths and normalizing stress tensors to USIF Voigt order `(xx, yy, zz, yz, xz, xy)`.
- Added interop contract tests for type guards, unsupported object errors, ASE dependency wording, and stress tensor normalization.
- Updated release metadata to the date record `20260605.007` and release ID `usif-20260605-007`.

# Changelog

## 6.3.0

- Persisted `.usifc` secondary indexes (`geometry_index`, `formula_index`, and `property_index`) inside the checksummed container index generation.
- Read-only container opens now load secondary indexes from the index payload instead of decoding every record before the first formula/property/geometry query.
- Added property-index support for scalar, vector, tensor, and dotted custom-property values using JSON-normalized hashable keys.
- Added explicit validation levels: `validate(level="index")`, `validate(level="records")`, and `validate(level="full")`. The older `decode_records=True` convenience flag maps to `level="full"`.
- Reworked `rebuild_index()` to scan record bytes in bounded reads instead of materializing the whole container file.
- Added reliability tests for persisted secondary indexes, validation levels, and streaming rebuild behavior.
- Added `large` and `performance` pytest markers for future container-scale checks.
- Updated release metadata to the date record `20260605.006` and release ID `usif-20260605-006`.
- Kept binary `FORMAT_VERSION` at 5 because the `.usif` single-record format did not change.

## 6.2.0

- Added ergonomic property management APIs for structure-level and atom-level values.
- `StructureProperties` and `AtomicProperties` now support `get()`, `set()`, `remove()`, `has()`, `set_scalar()`, `set_vector()`, `set_tensor()`, and `set_custom()`.
- `USIFStructure` now provides pure-model property helpers: `set_structure_property()`, `get_structure_property()`, `set_atom_property()`, `get_atom_property()`, `set_atomic_property()`, and `get_atomic_property()`.
- Built-in scalar/vector/tensor values are normalized and validated consistently; structure stress accepts either Voigt `(xx, yy, zz, yz, xz, xy)` or a 3x3 tensor matrix.
- Custom properties are normalized to JSON-compatible values so `.usif`, `.json`, `.usif.json`, and container records preserve scalars, vectors, tensors, nested dictionaries, booleans, and nulls.
- Added `examples/07_property_management.py` and focused property-management regression tests.
- Updated release metadata to the date record `20260605.005` and release ID `usif-20260605-005`.

## 6.1.0

- Added official USIF JSON structure support with schema marker `usif.structure.json.v1`.
- Added `usif.services.json_io` with `save_structure_json()`, `load_structure_json()`, `structure_to_json_dict()`, and `structure_from_json_dict()`.
- Updated `save_structure()` and `load_structure()` to support `.json` and `.usif.json`; unsupported extensions now fail explicitly.
- Updated `export_structure()` to route `fmt="json"` / `.json` filenames through the official JSON service.
- Made `USIFStructure.as_dict()` return JSON-compatible structure-property dictionaries.
- Narrowed the public `usif.storage` API to `StructureContainer`, `USIFGroup`, and `ContainerValidationResult`; internal stores and mixins remain available from concrete submodules.
- Removed remaining `__main__` demo blocks from property library modules.
- Added zip extraction size/member guards to Materials Project archive loading.
- Updated Materials Project examples documentation to the current grouped `group_XX/materials.json` workflow.
- Added `examples/06_json_structure_roundtrip.py` and corresponding smoke tests.
- Updated the pyproject-driven release metadata to the unique date record `20260605.004` and release ID `usif-20260605-004`.
- Kept binary `FORMAT_VERSION` at 5 because the `.usif` single-record format did not change.

## 6.0.0

- Promoted the package classifier to stable status for the 6.0 architecture line.
- Moved the editable package version source to `[project].version` in `pyproject.toml` instead of a dynamic setuptools attribute.
- Added `[tool.usif.release]` with a date-based unique release record (`20260605.002`) and release ID (`usif-20260605-002`).
- Added `usif.RELEASE_DATE`, `usif.RELEASE_RECORD`, and `usif.RELEASE_ID` exports.
- Added `docs/VERSIONING.md` to document the pyproject-driven release metadata scheme.
- Folded the low-level `file_store` helper into `RecordStore` as `ChunkedRecordAccess`, keeping container storage internals tighter for 6.0.
- Added `StructureContainer.validate()` and `ContainerValidationResult` for explicit index/group/record consistency checks.
- Kept binary `FORMAT_VERSION` at 5 because the USIF record format did not change.

## 5.9.0

- Reorganized tests into explicit `tests/unit`, `tests/integration`, `tests/reliability`, `tests/examples`, and `tests/fixtures` layers.
- Added pytest markers for unit, integration, interop, MP fixture data, network, slow, reliability, and examples; markers are applied from directory layout by `tests/conftest.py`.
- Moved bundled Materials Project test data from `tests/data` to `tests/fixtures`.
- Added GitHub Actions CI covering formatting, type checks, security scans, dependency audit, Python 3.10–3.12 unit tests, integration/reliability/example tests, sdist/wheel build, and wheel install smoke test.
- Added `docs/TESTING.md` and `docs/RELEASE.md` for the new validation and release process.
- Removed `setup.cfg` and local pytest/build metadata from the source tree; `pyproject.toml` is now the packaging configuration source.
- Raised the coverage gate to 80%.
- Updated `MANIFEST.in` to exclude archive docs, caches, build outputs, and egg-info from release artifacts.
- Kept binary `FORMAT_VERSION` at 5 because the USIF record format did not change.

## 5.8.0

- Removed the generic `usif.utils` package.
- Moved structure optimization to `usif.services.optimizer` and exported `USIFOptimizer` / `optimize_structure` from `usif.services`.
- Moved compression benchmarking to `usif.benchmarks.compression` and exported `USIFBenchmark` / `benchmark_compression` from `usif.benchmarks`.
- Split Materials Project tooling into `usif.integrations.materials_project` modules for client access, query presets, downloading, archive safety, group loading, and MP document mapping.
- Updated tests, examples, README, and architecture documentation to use explicit service/benchmark/integration imports.
- Removed the `usif.utils.*` mypy ignore override; only interop adapters remain temporarily ignored.
- Kept binary `FORMAT_VERSION` at 5 because the USIF record format did not change.

## 5.7.0

- Split pymatgen import logic into `CrystalImporter` and `MoleculeImporter`, with `PymatgenImporter` now acting as a small dispatch facade.
- Split pymatgen export logic into `CrystalExporter` and `MoleculeExporter`, with `PymatgenExporter` dispatching to focused exporters.
- Added `usif.interop.pymatgen.property_extractor` for shared atomic-property and structure-property normalization.
- Added `SymmetryPolicy` to make import/reduction symmetry behavior explicit instead of scattering boolean decisions through importer code.
- Added `extract_point_group_sites()` as the shared molecule point-group extraction path used by both importer and reducer.
- Updated `usif.symmetry.__init__` to avoid eager importing `SymmetryReducer`; reducer is now resolved lazily.
- Updated architecture tests and documentation to enforce focused interop/symmetry boundaries.
- Kept binary `FORMAT_VERSION` at 5 because the USIF record format did not change.

## 5.6.0

- Slimmed `USIFStructure` into a pure domain model: removed `from_source()`, `from_pymatgen()`, `to()`, `save()`, and `load()` from the model class.
- Added `usif.services` as the canonical application boundary for `import_structure()`, `import_pymatgen()`, `export_structure()`, `save_structure()`, and `load_structure()`.
- Removed obsolete `usif.structures.source`, `usif.structures.io`, and `usif.io` modules.
- Updated examples, tests, and README to use service functions or explicit interop adapters.
- Updated Materials Project conversion utilities to import through the service layer instead of model class methods.
- Kept binary `FORMAT_VERSION` at 5 because the USIF record format did not change.

## 5.5.0

- Added composed `RecordStore` and `ContainerIndexStore` components for container file and index I/O.
- Moved chunk allocation/read/write behind `RecordStore` instead of constructing file adapters in the container.
- Reworked container index loading to read the fixed header and referenced index block instead of materializing the whole `.usifc` file.
- Added bounded streaming recovery scan for invalid header index offsets.
- Updated storage architecture tests to enforce composed store boundaries and bounded index reads.

## 5.4.0

- Replaced the dual property registry implementation with a single instance-based `PropertyRegistry`.
- Added `DEFAULT_REGISTRY` and `create_default_registry()` as the canonical registry entry points.
- Removed `PropertyRegistryInstance`, class-level registry methods, and registry compatibility facades.
- Removed encoder private compatibility helpers and the `calculate_structure_hash()` alias.
- Renamed container `hash_index` terminology to `record_index`.
- Removed library-module demo blocks from the property registry implementation.

## 5.3.0

- Removed backward-compatibility modules: `usif.converter`, `usif.container`, `usif.interop.converter_core`, `usif.interop.symmetry`, and `usif.io.facade`.
- Moved pymatgen conversion implementation into `usif.interop.pymatgen.importer` and `usif.interop.pymatgen.exporter`; ASE adapters now call those canonical adapters directly.
- Updated internal calls, examples, and tests to use canonical imports from `usif.storage`, `usif.interop.pymatgen`, and `usif.interop.ase`.
- Renamed priority-numbered tests to capability-based names.
- Kept binary `FORMAT_VERSION` at 5 because the USIF record format did not change.

### Additional architecture cleanup carried forward

- Fixed `to_pymatgen` site-property length mismatch: `_to_crystal` and `_to_molecule` now build index-aligned `forces`/`charges`/`magmoms` lists, filling missing per-atom values with neutral defaults instead of skipping them (previously raised when only some atoms carried a property).
- Unified crystal Wyckoff extraction into `usif.symmetry.analysis.extract_wyckoff_sites`, used by both the pymatgen importer and `SymmetryReducer` (removed the duplicated `SpacegroupAnalyzer` extraction logic).
- `SymmetryReducer.reduce_crystal` / `reduce_molecule` no longer mutate the input structure: symmetry metadata is written onto a deep-copied `structure_properties` carried by the returned structure.
- Separated numeric-property query tolerance from coordinate/symmetry tolerance via `QueryConstants.DEFAULT_NUMERIC_TOLERANCE`; container/query numeric matching no longer borrows `SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE`.
- Removed dead code: unused converter delegators (`_coords_equal`, `_site_sets_equal`, `_contains_coord`) and unused `interop/*/property_mapping.py` placeholder modules.

### Engineering governance carried forward

- Cleaned and verified README examples.
- Added runnable examples for quickstart, container query, conversion, properties, and hash semantics.
- Expanded CI to Python 3.10–3.12, coverage, example smoke tests, build artifact install smoke tests, lint/type/security checks, and dependency audit.
- Added black, mypy, bandit, pip-audit, and coverage configuration.
- Cleaned `MANIFEST.in` and moved package version source to `usif.version.__version__`.
- Added focused documentation for container format, property system, contributing, and changelog.
- Archived historical review and planning documents under `docs/archive/`.


## 5.2.0

- Split `usif.storage.container` into focused storage components: attribute codec, LRU cache, group operations, chunked I/O adapter, index persistence, prefetch/batch reads, and recovery scanner.
- Reduced `StructureContainer` to a coordination layer while preserving public container APIs.
- Removed obsolete unchecked container compatibility paths for raw legacy index payloads and lossy string attribute decoding.
- Added storage architecture tests to enforce the new boundaries and prevent the monolith from returning.
- Kept binary `FORMAT_VERSION` at 5 because the USIF record format did not change.

## 5.1.0

### Baseline and container reliability

- Raised the package baseline to Python 3.10+ and version 5.1.0.
- Added `monty` as an explicit core dependency because core structure JSON I/O imports it directly.
- Replaced stale `run_lint.py` documentation with direct black/isort/mypy/bandit commands.
- Fixed `usif.services / usif.benchmarks / usif.integrations.__all__` by exporting the documented convenience aliases.
- Container deduplication now keeps byte-level de-duplication while still recording new aliases, groups, and attributes for duplicate records.
- Container structure and group attributes are persisted through a JSON typed codec instead of lossy string conversion.
- Read-only containers now reject structure attribute mutation.
- Parallel batch retrieval now preserves order when duplicate identifiers are requested.
- Context-manager close failures no longer mask an exception that was already active inside the `with` block.
