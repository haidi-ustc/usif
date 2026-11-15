# Format Versioning

USIF tracks three related but separate version concepts.  They must not be
collapsed into a single value because package releases can change documentation,
APIs, tests, or container metadata without changing the binary record layout.

## Package version

The public Python package version lives in `pyproject.toml`:

```toml
[project]
version = "0.7.1"
```

This value changes for every published package release.  Source-tree imports read
it from `pyproject.toml`; installed wheels expose it through package metadata.

## Date-based release record

The release audit record also lives in `pyproject.toml`:

```toml
[tool.usif.release]
date = "2026-06-05"
sequence = 16
record = "20260605.016"
id = "usif-20260605-016"
```

Rules:

- `record` is always `YYYYMMDD.NNN`.
- `id` is always `usif-YYYYMMDD-NNN`.
- `sequence` increments for each release produced on the same date.
- `scripts/check_release_metadata.py` validates the pyproject record, baked wheel
  fallback constants, CI wheel smoke expectations, and the latest changelog entry.

## `.usif` binary record format version

The single-structure `.usif` binary record format is versioned independently by
`usif.version.FORMAT_VERSION`.  In 0.8.0 it is:

```python
FORMAT_VERSION = 6
```

Encoders always write the current `FORMAT_VERSION`.  Decoders accept every
version listed in `SUPPORTED_FORMAT_VERSIONS` (currently 5 and 6) and select the
body layout from the record header, so files and containers written by earlier
releases stay readable.  `tests/fixtures/format5` holds golden format-5 records
that must keep decoding to the same structures.

Bump `FORMAT_VERSION` only when existing binary `.usif` records need new reader
logic or migration behavior.  Examples include changing header layout, changing
compression enum values, changing payload section ordering, or changing checksum
semantics.

## `.usifc` container format version

The container wrapper has its own header and index manifest layout documented in
`docs/CONTAINER_FORMAT.md`.  Package releases may extend the checksummed index
payload while keeping `.usif` records at the same `FORMAT_VERSION`.  Reader code
must reject unsupported container manifest versions with clear errors and should
prefer recovery/validation tools for damaged indexes.

## Release checklist

Before publishing a source or wheel artifact:

```bash
python scripts/check_release_metadata.py --write-report release-checks.txt
python -m build
```

The generated `release-checks.txt` can be distributed next to the package archive
and `sha256sums.txt` for auditability.


## 0.8.0 release note

`0.8.0` is recorded as `20261115.017`. It bumps the `.usif` binary record format to
`FORMAT_VERSION = 6`: symmetric crystals now store the spglib Hall number and the
setting transformation `(P, p)` so expansion reproduces the stored cell exactly,
symmetric site counts and multiplicities widen to `uint32`, and symmetric records
no longer depend on an external library's setting tables. Format-5 records are
still decoded, with a frozen space-group -> Hall table. The `.usifc` container
layout is unchanged.

## 0.7.1 release note

`0.7.1` is a legacy-cleanup package release recorded as `20260605.016`. It keeps the `.usif` binary record `FORMAT_VERSION = 5` and tightens the `.usifc` container manifest line to container version 2 with `USIFIDX2` / `SIDX0002` index markers.
