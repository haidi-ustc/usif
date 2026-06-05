# Changelog

## Unreleased

### P4 architecture cleanup

- Fixed `to_pymatgen` site-property length mismatch: `_to_crystal` and `_to_molecule` now build index-aligned `forces`/`charges`/`magmoms` lists, filling missing per-atom values with neutral defaults instead of skipping them (previously raised when only some atoms carried a property).
- Unified crystal Wyckoff extraction into `usif.symmetry.analysis.extract_wyckoff_sites`, used by both the pymatgen importer and `SymmetryReducer` (removed the duplicated `SpacegroupAnalyzer` extraction logic).
- `SymmetryReducer.reduce_crystal` / `reduce_molecule` no longer mutate the input structure: symmetry metadata is written onto a deep-copied `structure_properties` carried by the returned structure.
- Separated numeric-property query tolerance from coordinate/symmetry tolerance via `QueryConstants.DEFAULT_NUMERIC_TOLERANCE`; container/query numeric matching no longer borrows `SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE`.
- Removed dead code: unused converter delegators (`_coords_equal`, `_site_sets_equal`, `_contains_coord`) and unused `interop/*/property_mapping.py` placeholder modules.

### P3 engineering governance

- Cleaned and verified README examples.
- Added runnable examples for quickstart, container query, conversion, properties, and hash semantics.
- Expanded CI to Python 3.8–3.12, coverage, example smoke tests, build artifact install smoke tests, lint/type/security checks, and dependency audit.
- Added black, mypy, bandit, pip-audit, and coverage configuration.
- Cleaned `MANIFEST.in` and moved package version source to `usif.version.__version__`.
- Added focused documentation for container format, property system, contributing, and changelog.
- Archived historical review and planning documents under `docs/archive/`.
