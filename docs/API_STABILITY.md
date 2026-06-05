# API Stability Policy

USIF 7.x is the stable architecture line.  The public API is intentionally small;
internal modules may keep changing when they improve reliability, performance, or
maintainability.

## Public API

The following entry points are considered stable for 7.x minor releases:

- `usif.USIFStructure`
- `usif.USIF`
- `usif.properties.PropertyRegistry`
- `usif.properties.DEFAULT_REGISTRY`
- `usif.properties.create_default_registry()`
- `usif.storage.StructureContainer`
- `usif.storage.USIFGroup`
- `usif.storage.ContainerValidationResult`
- `usif.services.import_structure()`
- `usif.services.import_pymatgen()`
- `usif.services.export_structure()`
- `usif.services.save_structure()`
- `usif.services.load_structure()`
- `usif.services.save_structure_json()`
- `usif.services.load_structure_json()`
- `usif.interop.pymatgen.PymatgenImporter`
- `usif.interop.pymatgen.PymatgenExporter`
- `usif.interop.ase.ASEImporter`
- `usif.interop.ase.ASEExporter`
- `usif.benchmarks.benchmark_compression()`
- `usif.integrations.materials_project` high-level functions documented in README
- `usif` console script and `usif.cli.main()` programmatic CLI entry point

## Internal API

Modules under storage implementation boundaries, low-level index stores, mixins,
recovery scanners, binary codec helpers, and test utilities are internal unless
explicitly listed above.  They are safe to import for advanced experiments, but
minor releases may change them without deprecation.

Examples of internal modules:

- `usif.storage.index_persistence`
- `usif.storage.io_ops`
- `usif.storage.prefetch`
- `usif.storage.recovery`
- `usif.format.binary.*`

## Experimental API

Features marked experimental in documentation or docstrings may change within the
7.x line.  Examples include performance markers, large-container benchmarking
fixtures, and future optional native ASE conversion paths.

## Deprecation policy

The 7.x line should avoid reintroducing broad backward-compatible facades.  When a
public API must change:

1. Add a changelog entry explaining the reason.
2. Update README, examples, and architecture docs in the same release.
3. Add or update tests that describe the new public contract.
4. Prefer one minor release with a clear warning only when the old API is widely
   documented.  Otherwise, remove internal APIs directly.

## Breaking changes

Breaking changes to the stable public API should normally wait for 8.0.  Breaking
changes to undocumented internal modules are allowed in 7.x when tests and docs
are updated.
