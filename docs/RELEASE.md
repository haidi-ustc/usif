# Versioning and releases

## Version numbers

`pyproject.toml` is the single source of the package version and the release record:

```toml
[project]
version = "0.12.0"

[tool.usif.release]
date = "2026-11-26"
sequence = 21
record = "20261126.021"
id = "usif-20261126-021"
```

**Bump policy.** USIF is pre-1.0 (it was renumbered from `7.1.0` to `0.7.1` with identical
code). Releases bump the **minor** version (`0.11.0` -> `0.12.0`); patch releases (`0.12.1`) are
for fixes only. A major version (`1.0.0`) is a deliberate decision, never an automatic bump.

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
   assert usif.__version__ == "0.12.0"
   assert usif.RELEASE_RECORD == "20261126.021"
   from usif import Cell, Dataset, Structure, decode, encode
   s = Structure.from_fractional(["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(5.64))
   assert decode(encode(s)) == s
   print("USIF wheel smoke OK", usif.__version__)
   PY
   ```

The wheel contains only the `usif` package; tests, examples, docs and `scripts/` ship in the
source archive.
