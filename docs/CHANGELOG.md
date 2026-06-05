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
