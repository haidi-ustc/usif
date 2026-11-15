# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m pip install -e ".[dev,pymatgen,ase,mp]"      # dev install (CI uses this for lint + integration)

# Tests — always run from the repo root (several tests read paths like Path("usif/..."))
python -m pytest tests/unit
python -m pytest tests/integration tests/reliability tests/examples
python -m pytest tests/unit/storage/test_container.py::TestName::test_name   # single test
python -m pytest -m "not slow and not network"

# CI quality gates (all must pass)
black --check usif tests examples
isort --check-only usif tests examples
mypy usif
bandit -q -r usif -x tests
python scripts/check_release_metadata.py
```

Formatting is black/isort with line length 100. Coverage gate is `fail_under = 80`. Markers (`unit`, `integration`, `reliability`, `examples`, ...) are applied automatically from the `tests/<layer>/` directory by `tests/conftest.py`, so don't add them by hand. Materials Project tests use the bundled `tests/fixtures/mp_structures` data unless `MP_DATA_DIR` is set.

## Architecture

USIF is a library plus file formats for atomistic structures: single-record binary `.usif`, official JSON (`.json`/`.usif.json`, schema `usif.structure.json.v1`), and multi-record `.usifc` containers. `docs/ARCHITECTURE.md` is the authoritative code-facing description. `docs/BINARY_FORMAT.md` and `docs/CONTAINER_FORMAT.md` specify the on-disk layouts.

**Layering, enforced by tests in `tests/unit/imports` and `tests/unit/model`:**

- `usif/structures`: `USIFStructure` is a *pure model* (data, validation, `as_dict`/`from_dict`, equality). It must not import services, interop, storage, or the encoder, and must not grow `from_pymatgen()`, `to()`, `save()`, `load()` or similar. All conversion and I/O goes through `usif.services` (`import_structure`, `export_structure`, `save_structure`, `load_structure`, `optimize_structure`).
- `usif/format`: the `.usif` codec. `usif/encoder.py`'s `USIF` is a facade over `format/binary/` (`header`, `structure_codec`, `property_codec`, `reader`/`writer` with bounds checks, `limits`, `integrity`), plus `format/compression.py` and `format/hashing.py`.
- `usif/storage`: `StructureContainer` (`container.py`) is a facade that stores encoded `.usif` records. Chunk/mmap I/O lives in `record_store.py`; the CRC'd index blocks and commit marker in `index_store.py`/`index_persistence.py`; secondary indexes/query/groups/cache/recovery in their own modules. Storage depends on the codec, never the reverse.
- `usif/properties`: a `PropertyRegistry` with definitions and units, injectable rather than global-only. `PropertySerializer` is a thin facade over `properties/serializers/*`. Unit strings are normalized (`Å^2`, `eV/Å`) but values are never converted.
- `usif/interop`: `interop/common` is the backend-neutral array layer (`AtomsData`, `build_structure`, `structure_to_arrays`, `import_atoms`) plus import-free type guards. The `matsimpy`, `pymatgen` and `ase` adapters (`interop/<backend>/adapter.py`) only map their objects to and from `AtomsData`; they are independent (ASE does not need pymatgen).
- The core depends only on numpy + spglib. matsimpy/pymatgen/ASE are optional extras and must never be imported at module level outside `interop/<backend>/` and the lazy file readers in `services/convert.py`; `test_core_imports_no_optional_structure_library` enforces this. Tests that need a backend use `pytest.importorskip`. matsimpy is not on PyPI (installed from its source checkout), so CI skips its tests.
- `usif/symmetry` (spglib: `spacegroup.py`, `reduce.py`, `expand.py`, `tables.py`, `policies.py`), `usif/services/optimizer.py`: symmetry reduction and expansion. `usif/formula.py`/`usif/elements.py` own the reduced formula (replicates pymatgen's ordering).

**Two storage modes (`StorageMode`)** run through every layer:
- `FULL_ATOMIC`: explicit `atom_sites` with per-atom properties (forces, charges, magmoms, custom).
- `SYMMETRIC`: format-6 crystals store the spglib Hall number plus the setting transformation `(P, p)` (`x_std = P x + p`, omitted via flags when identity/zero) and Wyckoff representatives in the stored cell. `symmetry/expand.py` rebuilds the full structure with `W = P⁻¹RP`, `w = P⁻¹(Rp + t − p)` plus the lattice translations of `P⁻¹` (supercells).
  - Format-5 records (spacegroup number only) are expanded via the frozen `FORMAT5_SPACEGROUP_HALL` / `FORMAT5_POINT_GROUP_ROTATIONS` tables in `symmetry/tables.py`; the golden fixtures in `tests/fixtures/format5` must keep decoding identically. Never change those tables.
  - Reduction is always lossless: candidates at several symprec values must re-expand to every original atom within `SymmetryConstants.LOSSLESS_TOLERANCE` (1e-5 Å, float32-rounded), even with `force_symmetric`/`mode="reduce"`; otherwise the structure stays FULL_ATOMIC. Molecules are never reduced.
  - Symmetric records carry no per-atom properties; `SymmetryPolicy` (`symmetry/policies.py`, `apply_symmetry_policy`) decides between reducing, falling back, and dropping atomic properties.
  - Expansion reorders atoms (sorted by Z, then coords).

**Hashes** (`format/hashing.py`) have distinct meanings and should not be mixed:
- `geometry_hash` covers geometry only, as float32. It is stored in the header and checked on decode. The symmetry setting is included only when non-default, so format-5 hashes are unchanged.
- `record_hash` covers the full logical record, including properties, computed on the canonical (encode→decode) structure.
- `payload_digest` covers the encoded bytes.

## Guardrails that tests enforce

- `tests/unit/imports/test_legacy_cleanup.py` and `tests/unit/storage/test_storage_architecture.py` fail if any file under `usif/` contains (case-insensitive in the latter) "legacy", "historical", "backward-compatible", "compatibility facade", "transitional", "old fallback", "older payload", "alias for add", or "P1 "/"P2 "/"P3 ". Avoid these words in comments, docstrings and identifiers too: say "format-5" rather than "legacy" when referring to old records, and write the triclinic space group as "P-1" or "space group 1", never "P1 ".
- `StructureContainer` has exactly one add method (`add`, not `add_structure`).
- The property codec lives only in `usif/format/binary/property_codec.py`.

## Versioning and release metadata

**Bump policy:** the project is pre-1.0. It was renumbered from 7.1.0 to `0.7.1` (current: `0.8.0`); older CHANGELOG headings keep their historical numbers. Releases bump the *minor* version (0.8.0, 0.9.0, …), patch versions are for fixes only, and a new *major* (1.0.0) only happens when the user explicitly asks.

`pyproject.toml` is the single source: `[project].version` plus `[tool.usif.release]` (date, sequence, record, id). `usif/version.py` reads it from a source checkout and otherwise uses baked `_FALLBACK_*` constants.

A release bump must update all of the following together, or `scripts/check_release_metadata.py`, `tests/unit/imports/test_release_versioning.py`, and the CI wheel smoke step will fail:
- `pyproject.toml`
- the `_FALLBACK_*` constants in `usif/version.py`
- `docs/CHANGELOG.md`
- the hard-coded version and record strings in `.github/workflows/ci.yml` and `docs/RELEASE.md`

`FORMAT_VERSION` in `usif/version.py` is the `.usif` binary format version (currently 6; the decoder also reads 5 via `SUPPORTED_FORMAT_VERSIONS`). It changes only when the record layout changes; see `docs/FORMAT_VERSIONING.md`.
