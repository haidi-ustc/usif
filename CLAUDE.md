# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m pip install -e ".[dev,pymatgen,ase]" -r scripts/materials_project/requirements.txt
# editable dev install; keeps the `usif` command in sync with the source (a stale non-editable
# install shadows it). The requirements file is for the Materials Project script only.

# Tests — run from the repo root
python -m pytest tests/unit
python -m pytest tests/integration tests/reliability tests/examples
python -m pytest tests/unit/dataset/test_dataset.py::test_name    # single test
python -m pytest -m "not slow and not network"
# live LLM test: needs DEEPSEEK_API_KEY in the environment (marked network, skipped otherwise)

# CI quality gates (all must pass)
black --check usif tests examples scripts
isort --check-only usif tests examples scripts
mypy usif
bandit -q -r usif -x tests
python scripts/check_release_metadata.py

python -m scripts.benchmark -h              # size/speed of the encoding options
python -m scripts.materials_project -h      # MP download / dataset build (needs scripts/materials_project/requirements.txt)
```

Formatting is black/isort with line length 100. Coverage gate is `fail_under = 80`, applied to the whole suite
(`pytest tests --cov=usif`, the CI `integration` job); the unit layer alone reports coverage
with `--cov-fail-under=0` because `io`, `upgrade` and the backends are covered by integration tests. Markers
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
  SHA-256 geometry hash) and `container_v2.py` (v2 containers, used by `Dataset.import_v2`; there is
  no `usif upgrade` command). Do not change their behaviour; golden fixtures live in `tests/fixtures/format5`
  and `tests/fixtures/format6` (`generate.py` there was run against the real 0.8.0 code).
- `usif/backends`: `Backend` protocol + registry (matsimpy → ase → pymatgen → `usif.backends`
  entry points). Backends only map library objects/files to and from `Structure`.
- `usif/io.py`: `read/read_all/write/write_all/convert` dispatch — native suffixes to the codec,
  format-5/6 records to `upgrade`, everything else to a backend.
- `usif/agent`: local-dataset import and the LLM data agent (CLI-first, no GUI). `discover.scan`
  finds VASP directories and structure files and builds `Candidate`s with provenance attrs
  (`source`, `source_sha256`, `incar`, `notes`, ...). `plan.Plan` (JSON `usif.agent.plan.v2`, id =
  hash of format + content; v1 plans of 0.10/0.11 are refused, not converted) and `apply_plan`, the only write path: it re-checks sources and runs in one
  transaction. `tools.Toolbox` holds read-only tools plus `propose_*` tools that only extend the
  plan. `session.Session` is the tool loop, and `llm.ChatClient` is OpenAI-compatible HTTP (stdlib)
  with DeepSeek as the default (`config.py`; key only from the env var named by `api_key_env`).
  `config.agent_dataset` resolves the dataset of `ask`/`chat`: the argument, else `USIF_DATASET`,
  else `[agent] dataset` in `~/.usif/config.toml`; a default must be absolute and exist (never
  guessed, never created). The agent has no file-writing tool: exports are `usif dataset export`
  (query or `--entry` -> one file, refuses an existing file without `--overwrite`).
- `usif/cli/` is Typer (never import click directly): `root.py` (app, file commands, `main`),
  `dataset.py`, `agent.py`, `plans.py` (the approval step both groups share), `common.py`. Conventions, covered by
  `tests/integration/test_cli.py`: `-h` and `--help` everywhere (`context_settings`); a bare command
  group prints help and exits 0; usage errors exit 2; `USIFError`/`OSError`/`KeyError` print one
  line `usif: error: ...` and exit 2, never a traceback; `validate` exits 1 when invalid. The
  script CLIs in `scripts/` follow the same rules.

**Hashes** (`codec/record.py`): `record_hash` = BLAKE2b-256 of the raw payload (identity and
dataset dedup; encoding options are part of it); `geometry_hash` = BLAKE2b-256 of the payload up to
the end of `POSN`/`SYMM`; the header digest covers the stored (compressed) bytes.

## Guardrails that tests enforce (`tests/unit/architecture/test_architecture.py`)

- The import-layer table (`ALLOWED`): basics ← model ← symmetry ← codec ← upgrade (only
  `codec.wire`) ← dataset; backends see only model; io sees codec/upgrade/backends; agent sees
  model/dataset/io; cli sees all. Imports inside functions count too. A new top-level module must be added to the table.
- Optional libraries (`ase`, `pymatgen`, `matsimpy`, `zstandard`, `mp_api`, `monty`) are never
  imported at module level. The core depends only on numpy, spglib and typer.
- No relative imports inside `usif/`. Applications (benchmarks, Materials Project tooling) live in
  `scripts/`, which is not packaged; `usif/integrations` and `usif/benchmarks.py` must not exist.
- No file under `usif/` may contain (case-insensitive) "legacy", "historical",
  "backward-compatible", "compatibility facade", "transitional", "old fallback", "older payload",
  "alias for add", or "P1 "/"P2 "/"P3 ". Say "format 5/6" or "USIF 0.8 files"; write the triclinic
  space group as "P-1" or "space group 1".
- `usif/symmetry/tables.py` (format-5 tables) is fingerprinted by sha256: never edit it.

## Development principles

- **Avoid overengineering.** Prefer one clear mechanism over a plugin system; add registries only
  for the four extension points in `docs/ARCHITECTURE.md`. Breaking changes are fine pre-1.0 when
  they simplify the design; old files stay readable through `usif/upgrade`.
- **Exact by default, strict on input.** Lossy options are explicit (`precision="f32"`,
  `symmetry="auto"` within 1e-5 Å). Encoders cast to the declared wire type; decoders reject
  anything an encoder would not write. Validate at the boundary (`ValidationError` for user input,
  `FormatError` for bytes) instead of letting NumPy or SQLite errors escape.
- **Human in the loop.** The agent (LLM) never writes. Its tools open datasets read-only, read
  files only under `--allow` roots, and record changes as a `Plan`. Applying a plan needs a
  person: a `[y/N]` prompt, or `--yes` on `usif agent apply` / `usif dataset import`, never on
  `ask`/`chat`. Never put the API key in messages, plans, logs or output.
- **Physics.** Units are CODATA 2018; never silently reinterpret a value whose unit you cannot
  convert. Keep MP fields with MP's meaning (`energy` = uncorrected DFT total).
- **Measure before optimising.** Benchmark (`python -m scripts.benchmark`, or a dataset of ~30k
  entries), check `EXPLAIN QUERY PLAN` for dataset queries, and add a test that pins a fixed plan.
- **Docs are part of the change.** Update `docs/guide/`, the README, examples, the changelog and the
  reference docs with the code; run every snippet you keep. One page per topic, no duplicates.
- **Verify before claiming done:** all CI gates above, the full test suite, and both wheel smoke
  scripts (`.github/workflows/ci.yml` and `publish.yml` must track the public API).

## Git workflow

- Commit only when asked. Work on a feature branch, commit in logical, layered steps (each with a
  descriptive body), merge into `main` (`--no-ff` for a multi-commit feature, fast-forward for a
  single fix), push, then delete merged branches locally and on `origin` so only `main` remains.
- Never commit `newplan.md` or the user's uncommitted `.gitignore` edits.
- Pushing does not publish: `publish.yml` uploads to PyPI only on a GitHub release or a manual run.

## Versioning and release metadata

**Bump policy:** pre-1.0 (current `0.12.0`). Releases bump the *minor* version (0.9.0, 0.10.0, …),
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
