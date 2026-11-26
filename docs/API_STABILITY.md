# API stability

USIF is pre-1.0. Releases bump the minor version (0.10.0, 0.11.0, ...) and may change the public API; patch releases (0.9.1, ...) contain fixes only and do not change it.

USIF 0.9.0 is a breaking redesign. The 0.8 API (`USIFStructure`, `USIF`, `StructureContainer`, `usif.services`, `usif.interop`, `SymmetryPolicy`, `PropertyRegistry`, `AtomicProperties`/`StructureProperties`, `CompressionType`) was removed without a compatibility layer. The 0.9.0 entry of [CHANGELOG.md](CHANGELOG.md) has the migration guide.

## Public API

The public API is listed in [guide/api.md](guide/api.md). In short:

- the names exported by `usif` (`Structure`, `Cell`, `Schema`, `PropertySpec`, `DEFAULT_SCHEMA`, `read`, `read_all`, `write`, `write_all`, `convert`, `encode`, `decode`, `Dataset`, `Q`, the exceptions and the version constants);
- `usif.model`, `usif.codec` (including `jsondoc` and `compression`), `usif.dataset`, `usif.backends`, `usif.upgrade`, `usif.symmetry` (`analyze`), `usif.units`, `usif.errors`;
- the `usif` command line and `usif.cli.main()`;
- the extension points: property specs (`Schema.register`), compression codecs (`usif.codec.compression.register`), backends (`usif.backends.register` and the `usif.backends` entry-point group).

The development scripts in `scripts/` (benchmarks, Materials Project tooling) are not part of the package or its API.

## Internal API

Everything else is internal and may change in any release, including:

- `usif.codec.wire`, `usif.codec.columns` and the private helpers of `usif.codec.record`;
- `usif.dataset.sql` and the SQL text produced by `Q`;
- `usif.symmetry.spacegroup`, `usif.symmetry.tables` and the internals of `reduce`/`expand`;
- `usif.fileio`, `usif.elements`, `usif.formula`;
- names starting with an underscore.

## File formats

File formats are versioned independently of the package:

- `.usif` record format 7 (`usif.FORMAT_VERSION`), specified in [BINARY_FORMAT.md](BINARY_FORMAT.md);
- JSON documents with schema `usif.structure.json.v2`;
- `.usifc` dataset schema 1 (`usif.DATASET_SCHEMA_VERSION`), specified in [DATASET_FORMAT.md](DATASET_FORMAT.md).

A file written by a release stays readable by later releases. Files written by USIF 0.8 and earlier (record formats 5 and 6, container version 2) are read by the frozen readers in `usif.upgrade`; see [FORMATS_0_8.md](FORMATS_0_8.md) and [FORMAT_VERSIONING.md](FORMAT_VERSIONING.md).

## Changing the public API

When a public name changes:

1. Describe the change and the replacement in [CHANGELOG.md](CHANGELOG.md).
2. Update the README, `docs/guide/`, the examples and their tests in the same change.
3. Add or update tests for the new behaviour.
