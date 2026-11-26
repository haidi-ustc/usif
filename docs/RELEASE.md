# Versioning and releases

## Version numbers

`pyproject.toml` is the single source of the package version and the release record:

```toml
[project]
version = "1.0.0"

[tool.usif.release]
date = "2026-11-26"
sequence = 22
record = "20261126.022"
id = "usif-20261126-022"
```

**Bump policy.** USIF is at `1.0.0`: the public API listed in [API_STABILITY.md](API_STABILITY.md)
is stable. Patch releases (`1.0.1`) are fixes only, minor releases (`1.1.0`) add to the public API
without breaking it, and a major version (`2.0.0`) is a deliberate decision, never an automatic
bump.

**Release record.** `date` is the ISO release date, `sequence` increases by one with every
release, `record` is `YYYYMMDD.NNN` and `id` is `usif-YYYYMMDD-NNN`. A source checkout reads
these from `pyproject.toml`; an installed wheel uses the `_FALLBACK_*` constants baked into
`usif/version.py`.

The `.usif` record format and the dataset schema have their own version numbers, which change
only with their layouts; see [FORMAT_VERSIONING.md](FORMAT_VERSIONING.md).

## Release checklist

1. Update, together:
   - `[project].version` and `[tool.usif.release]` in `pyproject.toml`;
   - the `_FALLBACK_*` constants in `usif/version.py`;
   - `docs/CHANGELOG.md` (a new top entry naming the record and id);
   - the version and record in `.github/workflows/ci.yml`, in this file and in
     `tests/unit/release/test_release_versioning.py`.
2. Validate the metadata; the checker covers all of the above:

   ```bash
   python scripts/check_release_metadata.py --write-report release-checks.txt
   ```

3. Run the checks and tests listed in [CONTRIBUTING.md](CONTRIBUTING.md).
4. Build: `python -m build`.
5. Smoke-test the wheel in a clean virtual environment:

   ```bash
   python -m venv /tmp/usif-wheel-smoke
   /tmp/usif-wheel-smoke/bin/python -m pip install dist/*.whl
   /tmp/usif-wheel-smoke/bin/python - <<'PY'
   import usif
   assert usif.__version__ == "1.0.0"
   assert usif.RELEASE_RECORD == "20261126.022"
   from usif import Cell, Dataset, Structure, decode, encode
   s = Structure.from_fractional(["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(5.64))
   assert decode(encode(s)) == s
   print("USIF wheel smoke OK", usif.__version__)
   PY
   ```

The wheel contains only the `usif` package; tests, examples, docs and `scripts/` ship in the
source archive.

## Publishing

`.github/workflows/publish.yml` builds, checks and uploads the sdist and wheel. It uses PyPI
trusted publishing (OIDC), so no token is stored in the repository: publishing a GitHub release
whose tag is `v<project.version>` uploads to PyPI, and a manual run uploads to TestPyPI unless PyPI
is chosen. The one-time setup on pypi.org / test.pypi.org (project `usif` → Publishing) names the
workflow file, so it must match: owner `haidi-ustc`, repository `usif`, workflow `publish.yml`,
environment `pypi` (or `testpypi`). Renaming the workflow file means updating that entry as well.
