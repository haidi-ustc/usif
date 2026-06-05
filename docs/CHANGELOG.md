# Changelog

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
- Fixed `usif.utils.__all__` by exporting the documented convenience aliases.
- Container deduplication now keeps byte-level de-duplication while still recording new aliases, groups, and attributes for duplicate records.
- Container structure and group attributes are persisted through a JSON typed codec instead of lossy string conversion.
- Read-only containers now reject structure attribute mutation.
- Parallel batch retrieval now preserves order when duplicate identifiers are requested.
- Context-manager close failures no longer mask an exception that was already active inside the `with` block.
