# Contributing

## Setup

From a source checkout, with the development dependencies:

```bash
python -m pip install -e ".[dev,pymatgen,ase]" -r scripts/materials_project/requirements.txt
```

matsimpy is optional and not on PyPI; install it from its source checkout to run its tests.
Run every command below from the repository root.

`pytest` (or `python -m pytest`) run from the repository root always tests this checkout:
`pyproject.toml` sets `pythonpath = ["."]`, so the tests import `usif` and `scripts` from the
source tree even without an editable install, and an older `usif` installed in the same
environment cannot shadow it. The editable install is still how you get the dependencies and the
`usif` command.

## Checks

CI runs these; all must pass before a change is merged:

```bash
black --check usif tests examples scripts
isort --check-only usif tests examples scripts
mypy usif
bandit -q -r usif -x tests
pip-audit
python scripts/check_release_metadata.py
python -m pytest tests/unit --cov=usif --cov-fail-under=0   # fast; coverage reported only
python -m pytest tests --cov=usif --cov-report=term-missing  # whole suite; coverage gate: 80%
```

The coverage gate (`fail_under = 80` in `pyproject.toml`) applies to the whole suite, as in the
CI `integration` job. The unit layer alone stays below it, because `usif.io`, `usif.upgrade` and
the backends are exercised by the integration and reliability tests; the CI `unit` job (Python
3.10 to 3.12) reports its coverage without gating it.

black and isort use a line length of 100. Useful subsets:

```bash
python -m pytest tests/unit/codec/test_codec.py -k round_trip
python -m pytest -m "not slow and not network"
```

## Test layout

| Path | Contents |
|---|---|
| `tests/unit/model/` | `Structure`, `Cell`, property maps, schemas, units |
| `tests/unit/codec/` | Record format 7 (including wire types and canonical decoding), JSON documents, compression |
| `tests/unit/symmetry/` | Lossless reduction and expansion |
| `tests/unit/dataset/` | `.usifc` datasets, `Q` queries and their query plans |
| `tests/unit/architecture/` | Import layering, lazy optional imports, frozen tables, retired wording |
| `tests/unit/release/` | Version and release metadata consistency |
| `tests/integration/interop/` | matsimpy, ASE and pymatgen backends, unit conversion, `usif.read`/`write`/`convert` |
| `tests/integration/materials_project/` | The `scripts/materials_project` mapper and command line, on bundled fixtures |
| `tests/integration/test_cli.py` | The `usif` command line |
| `tests/reliability/test_upgrade.py` | Reading USIF 0.8 files against golden fixtures |
| `tests/examples/` | Every script in `examples/` and the benchmark script |
| `tests/fixtures/` | Test data: `format5/`, `format6/` (USIF 0.8 files) and `mp_structures/` |

Tests that need an optional library use `pytest.importorskip`. `tests/conftest.py` applies the
markers `unit`, `integration`, `interop`, `mp_data`, `reliability` and `examples` from the
directory, so do not add them by hand; `network`, `slow`, `large` and `performance` are for
individual tests. Live Materials Project access is never part of the default suite; set
`MP_DATA_DIR` to run the Materials Project tests on another local download.

## Guidelines

- Keep the package layering described in [ARCHITECTURE.md](ARCHITECTURE.md);
  `tests/unit/architecture/` enforces it.
- The core depends only on numpy, spglib and typer. Import optional libraries (matsimpy, ASE,
  pymatgen, zstandard) inside the function that needs them, never at module level.
- Applications that are not part of the library (benchmarks, Materials Project tooling) belong in
  `scripts/`, which is not packaged.
- `usif/upgrade/` and the format-5 tables in `usif/symmetry/tables.py` are frozen. They must keep
  decoding `tests/fixtures/format5` and `tests/fixtures/format6` exactly; never regenerate or edit
  those fixtures to make a test pass (`format6/generate.py` was run against the USIF 0.8.0 code).
- A change to the record or dataset layout needs a format version decision; see
  [FORMAT_VERSIONING.md](FORMAT_VERSIONING.md).
- Every script in `examples/` must be listed in `tests/examples/test_examples.py`.
- Public API changes follow [API_STABILITY.md](API_STABILITY.md); releases follow
  [RELEASE.md](RELEASE.md).
