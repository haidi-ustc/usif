# Format versioning

USIF has four version numbers for the package and its data files, plus the format name of the
data agent's change plans (below). They change for different reasons and are never merged into
one.

| Version | Where | Current | Changes when |
|---|---|---|---|
| package version | `pyproject.toml` `[project].version` | 0.11.0 | every release (see [RELEASE.md](RELEASE.md)) |
| release record | `pyproject.toml` `[tool.usif.release]` | `20261126.020` | every release |
| `.usif` record format | `usif.version.FORMAT_VERSION` | 7 | the record layout changes in a way readers must know about |
| dataset schema | `usif.version.DATASET_SCHEMA_VERSION` (SQLite `user_version`) | 1 | the `.usifc` tables change |

## Record format

Writers always write `FORMAT_VERSION`. `usif.read()` and `usif.decode()` read format 7, and
`usif.read()` also reads formats 5 and 6 through the frozen readers in `usif.upgrade`.

Most extensions need no new version:

* new data goes in typed columns (`ARRS`, `PROP`), which every reader already understands;
* optional data that older readers may ignore goes in an *ancillary* section (lower-case tag);
* a new compression codec gets a new id; readers without it fail with a clear error.

Bump `FORMAT_VERSION` only for changes an older reader would misread: the header, a critical
section's body, section order, or hash semantics. A bump adds a reader for the old version (or
moves the old code into `usif/upgrade/`), golden fixtures written by the old code, and a changelog
entry.

## Dataset schema

`Dataset` refuses a file whose `user_version` it does not know. A schema change bumps
`DATASET_SCHEMA_VERSION` and adds a migration that `Dataset` runs inside one transaction when it
opens an older file for writing.

## Change plans

Change plans (`usif.agent.plan.v2`, `usif.agent.plan.PLAN_FORMAT`) are JSON documents waiting for a
person's approval, not stored data, so only the current format is read. The format name changes
when the operations or their meaning change; the plan id hashes the format name with the
content. A plan of an earlier format (`usif.agent.plan.v1`, written by 0.10 and 0.11) is refused
with a message naming the format and is left on disk unchanged; it is made again rather than
converted.

## Earlier formats

| Written by | Format | Read by |
|---|---|---|
| USIF 0.7 | `.usif` format 5 | `usif.upgrade.format6` |
| USIF 0.8 | `.usif` format 6 | `usif.upgrade.format6` |
| USIF 0.7, 0.8 | `.usifc` container v2 | `usif.upgrade.container_v2`, `usif upgrade` |

The golden fixtures in `tests/fixtures/format5` and `tests/fixtures/format6` must keep decoding to
the same structures. [FORMATS_0_8.md](FORMATS_0_8.md) specifies these layouts.
