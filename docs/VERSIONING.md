# Versioning

USIF 0.8.x uses `pyproject.toml` as the single editable release metadata source.
The public package version is stored in `[project].version`, and the dated release
record is stored in `[tool.usif.release]`:

```toml
[project]
version = "0.8.0"

[tool.usif.release]
date = "2026-11-15"
sequence = 17
record = "20261115.017"
id = "usif-20261115-017"
```

## Version bump policy

USIF is pre-1.0. The package version was renumbered from `7.1.0` to `0.7.1`; the
code is identical. Releases bump the **minor** version first (`0.7.1` -> `0.8.0` ->
`0.9.0` ...); patch releases (`0.8.1`) are for fixes only. Moving to a new **major**
version (`1.0.0`) is a deliberate decision, never an automatic bump.

The release record is intentionally date-based and unique per release day:

- `date`: ISO calendar date of the release.
- `sequence`: monotonically increasing sequence for multiple releases on the same date.
- `record`: compact sortable key in `YYYYMMDD.NNN` form.
- `id`: human-readable release identifier in `usif-YYYYMMDD-NNN` form.

`usif.version` reads this metadata from `pyproject.toml` when imported from a
source checkout. Installed wheels expose the public version from package metadata
and retain the same dated release constants baked into `usif.version` by the
release process.

## Automated validation

Run the release metadata guard before packaging:

```bash
python scripts/check_release_metadata.py --write-report release-checks.txt
```

The checker verifies `pyproject.toml`, `usif/version.py` fallback constants, the latest `docs/CHANGELOG.md` entry, CI wheel-smoke expectations, and release documentation.
