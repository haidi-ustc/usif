# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m pip install -e ".[dev,pymatgen,ase,mp]"      # dev install (CI uses this for lint + integration)

# Tests — run from the repo root
python -m pytest tests/unit
python -m pytest tests/integration tests/reliability tests/examples
python -m pytest tests/unit/dataset/test_dataset.py::test_name    # single test
python -m pytest -m "not slow and not network"

# CI quality gates (all must pass)
black --check usif tests examples
isort --check-only usif tests examples
mypy usif
bandit -q -r usif -x tests
python scripts/check_release_metadata.py

python -m scripts.benchmark                 # size/speed of the encoding options
python -m scripts.materials_project --help  # MP download / dataset build (needs .[mp])
```

Formatting is black/isort with line length 100. Coverage gate is `fail_under = 80`. Markers
(`unit`, `integration`, `interop`, `reliability`, `examples`, ...) are applied automatically from the
`tests/<layer>/` directory by `tests/conftest.py`, so don't add them by hand. Tests that need
matsimpy/ASE/pymatgen/monty use `pytest.importorskip`; matsimpy is not on PyPI, so CI skips it.
Materials Project tests use `tests/fixtures/mp_structures` unless `MP_DATA_DIR` is set.

## Architecture

`docs/ARCHITECTURE.md` is the authoritative code-facing description. `docs/BINARY_FORMAT.md`
(`.usif` format 7), `docs/DATASET_FORMAT.md` (`.usifc` SQLite schema) and `docs/FORMATS_0_8.md`
(frozen 0.8 formats) specify the files. User documentation is `docs/guide/` (one page per topic,
indexed by `docs/README.md`); keep it, `README.md` and `examples/` in sync with API changes.
`PLAN.md` records the design rationale of the 0.9 redesign.

- `usif/model`: `Structure` is columns — `numbers` (uint8), Cartesian `positions` (float64), optional
  immutable `Cell` (+ `pbc`), per-atom `arrays` and structure `properties` (both `PropertyMap`s with
  dtype/shape/unit, validated through a `Schema`; `DEFAULT_SCHEMA` holds built-ins like `energy`,
  `force`, `stress`). No storage modes, no I/O methods on the model. Units are labels normalised by
  `usif/units.py`; stored values are never converted. Backends convert built-in quantities to the
  library's units with `units.convert` (CODATA 2018) via `backends.base.value_in`/`standard_value`
  and raise rather than export a wrong number. Stress is GPa, Voigt order, positive = tensile (ASE
  sign).
- `usif/symmetry`: spglib analysis, lossless reduction (`reduce.py`, 1e-5 Å, keeps atom order via a
  permutation) and expansion (`expand.py`). Symmetry is only an *encoding option*
  (`symmetry="auto"`), used when lossless and when it makes the stored record smaller.
- `usif/codec`: `record.py` (format 7: 40-byte header with BLAKE2b-64 digest, tagged sections
  `ATOM CELL POSN|SYMM ARRS PROP`, lower-case tags are ancillary/skippable), `columns.py` (typed
  column blocks), `wire.py` (bounds-checked reader/writer), `compression.py` (registry: none, zlib,
  lzma, zstd optional), `jsondoc.py` (`usif.structure.json.v2`). Encoding is deterministic and
  every field has one wire dtype (cast explicitly in the encoder); decoding accepts only canonical
  bytes (normalised units, canonical JSON, schema dtypes), so `encode(decode(b)) == b`.
- `usif/dataset`: `.usifc` is SQLite (application_id `0x55534946`, `user_version` =
  `DATASET_SCHEMA_VERSION`). Records are deduplicated by `record_hash`; entries are `(group, name)`
  with JSON attrs; `Q` compiles to parameterised SQL. `"w"` mode builds a temp file and replaces.
- `usif/upgrade`: frozen readers for USIF 0.8 files — `format6.py` (records formats 5/6, checks the
  SHA-256 geometry hash) and `container_v2.py` (v2 containers, used by `Dataset.import_v2` and
  `usif upgrade`). Do not change their behaviour; golden fixtures live in `tests/fixtures/format5`
  and `tests/fixtures/format6` (`generate.py` there was run against the real 0.8.0 code).
- `usif/backends`: `Backend` protocol + registry (matsimpy → ase → pymatgen → `usif.backends`
  entry points). Backends only map library objects/files to and from `Structure`.
- `usif/io.py`: `read/read_all/write/write_all/convert` dispatch — native suffixes to the codec,
  format-5/6 records to `upgrade`, everything else to a backend. `usif/cli.py` is Typer.

**Hashes** (`codec/record.py`): `record_hash` = BLAKE2b-256 of the raw payload (identity and
dataset dedup; encoding options are part of it); `geometry_hash` = BLAKE2b-256 of the payload up to
the end of `POSN`/`SYMM`; the header digest covers the stored (compressed) bytes.

## Guardrails that tests enforce (`tests/unit/architecture/test_architecture.py`)

- The import-layer table (`ALLOWED`): basics ← model ← symmetry ← codec ← upgrade (only
  `codec.wire`) ← dataset; backends see only model; io sees codec/upgrade/backends; cli sees all.
  Imports inside functions count too. A new top-level module must be added to the table.
- Optional libraries (`ase`, `pymatgen`, `matsimpy`, `zstandard`, `mp_api`, `monty`) are never
  imported at module level. The core depends only on numpy, spglib and typer.
- No relative imports inside `usif/`. Applications (benchmarks, Materials Project tooling) live in
  `scripts/`, which is not packaged; `usif/integrations` and `usif/benchmarks.py` must not exist.
- No file under `usif/` may contain (case-insensitive) "legacy", "historical",
  "backward-compatible", "compatibility facade", "transitional", "old fallback", "older payload",
  "alias for add", or "P1 "/"P2 "/"P3 ". Say "format 5/6" or "USIF 0.8 files"; write the triclinic
  space group as "P-1" or "space group 1".
- `usif/symmetry/tables.py` (format-5 tables) is fingerprinted by sha256: never edit it.

## Versioning and release metadata

**Bump policy:** pre-1.0 (current `0.9.0`). Releases bump the *minor* version (0.9.0, 0.10.0, …),
patch versions are for fixes only, and 1.0.0 only happens when the user explicitly asks. Older
CHANGELOG headings keep their historical numbers.

`pyproject.toml` is the single source: `[project].version` plus `[tool.usif.release]` (date,
sequence, record, id; the sequence increases by one per release). A release bump must update
together, or `scripts/check_release_metadata.py`, `tests/unit/release/test_release_versioning.py`
and the CI wheel smoke step fail:
- `pyproject.toml`
- the `_FALLBACK_*` constants in `usif/version.py`
- `docs/CHANGELOG.md` (latest heading plus record and id)
- the version and record strings in `.github/workflows/ci.yml`, `docs/RELEASE.md` and the release test

`FORMAT_VERSION` (7) and `DATASET_SCHEMA_VERSION` (1) in `usif/version.py` change only when the
record layout or the dataset tables change; see `docs/FORMAT_VERSIONING.md`.
