# Versioning

USIF 6.0 uses `pyproject.toml` as the single editable release metadata source.
The public package version is stored in `[project].version`, and the dated release
record is stored in `[tool.usif.release]`:

```toml
[project]
version = "6.0.1"

[tool.usif.release]
date = "2026-06-05"
sequence = 3
record = "20260605.003"
id = "usif-20260605-003"
```

The release record is intentionally date-based and unique per release day:

- `date`: ISO calendar date of the release.
- `sequence`: monotonically increasing sequence for multiple releases on the same date.
- `record`: compact sortable key in `YYYYMMDD.NNN` form.
- `id`: human-readable release identifier in `usif-YYYYMMDD-NNN` form.

`usif.version` reads this metadata from `pyproject.toml` when imported from a
source checkout. Installed wheels expose the public version from package metadata
and retain the same dated release constants baked into `usif.version` by the
release process.
