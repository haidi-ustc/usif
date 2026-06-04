# USIF Modernization and Improvement Plan (2025)

## Snapshot of Current State
- Core data model (`usif.structures`) and binary encoder remain stable and well covered by tests.
- Packaging metadata mixes `MIT` (in `pyproject.toml`) with a non-commercial license statement in `README.md`, creating compliance ambiguity.
- Container subsystem (`usif.container.StructureContainer`) still has known concurrency gaps and partial secondary indexing.
- Documentation is rich but spread across multiple Markdown files; no generated API reference or consolidated upgrade guide.
- CI/CD signals are absent in the repository; manual testing via `pytest` is documented but not enforced.

## Key Improvement Themes

### 1. Packaging and Release Governance
- Align declared license across `pyproject.toml`, `LICENSE`, and README; add explicit commercial licensing note if needed.
- Adopt isolated build backends (e.g., `hatchling`) or modernize setuptools configuration for reproducible builds.
- Introduce automated release workflow (GitHub Actions) that runs tests, builds wheels, and publishes to an internal index when tags are pushed.
- Add dependency upper bounds for heavy libraries (`pymatgen`, `numpy`) and configure Dependabot/Renovate.

### 2. Data Integrity and Validation
- Extend lattice and coordinate validation (positive volume, fractional bounds, unit checks) in `USIFStructure`.
- Enforce consistency between declared formula and actual composition; auto-generate when missing.
- Harden property array validation in converters, including shape/type enforcement and descriptive errors.
- Provide migration hooks for future `FORMAT_VERSION` changes (decode-time adapters, schema evolution notes).

### 3. Performance and Scalability
- Complete secondary index coverage in `StructureContainer`; make index depth configurable instead of fixed `[:10]`.
- Make index updates thread-safe by protecting mutation paths (`_update_secondary_indexes`, `_write_enhanced_index`) and adding concurrency tests.
- Add lazy loading / streaming APIs for large containers; profile memory impact using representative Materials Project archives.
- Benchmark alternative compression backends (LZMA, Zstandard) and expose as configurable options with sensible defaults.

### 4. Developer Experience
- Consolidate documentation into a Sphinx site with API reference, architecture diagrams, and format specification.
- Introduce type checking (`mypy`), linting (`ruff`), and formatting (`black`) in pre-commit hooks and CI.
- Publish example notebooks demonstrating round-trip conversions, property manipulation, and container analytics.
- Provide a structured changelog (Keep a Changelog) and clearly documented deprecation policy.

### 5. Ecosystem and Adoption
- Build a CLI entry point (`usif-cli`) for common tasks (convert, inspect, benchmark) to lower the adoption barrier.
- Offer plug-ins for ecosystem tools (ASE, pymatgen workflows) and document integration recipes.
- Define telemetry-friendly hooks (optional logging adapters) so downstream applications can monitor usage without modifying core code.

## Phased Roadmap

### Phase 0 – Foundations (Weeks 0-2)
- Resolve licensing inconsistency and update `LICENSE`/`pyproject.toml` metadata.
- Set up GitHub Actions (or preferred CI) running `pytest`, `ruff`, `mypy`, and packaging checks.
- Draft CONTRIBUTING guide outlining coding standards, tooling, and release process.

### Phase 1 – Stabilize and Validate (Weeks 3-8)
- Implement enhanced structure validation (lattice, coordinates, formula) and converter property checks.
- Refactor container indexing to remove hard-coded limits, add locking, and persist statistics.
- Write new tests covering concurrency, corrupted file recovery, and property edge cases; measure coverage.
- Establish automated documentation build using Sphinx + `docs/` sources.

### Phase 2 – Scale and Optimize (Months 3-5)
- Introduce lazy loading + streaming iterators for large container files; benchmark on Materials Project datasets.
- Add optional compression algorithms and expose tuning parameters; include regression benchmarks.
- Release CLI utilities with conversion, inspection, and validation commands, backed by integration tests.
- Publish official API docs and architecture diagrams; include upgrade/migration guide for prior USIF versions.

### Phase 3 – Extend and Engage (Months 6+)
- Develop plug-in system or adapter layer for external workflow engines (FireWorks, Atomate).
- Implement advanced query capabilities (composition filters, property ranges, similarity search) over containers.
- Evaluate telemetry/observability hooks and document privacy-conscious usage patterns.
- Run community beta program to collect feedback on new features; incorporate into roadmap revisions.

## Success Metrics
- CI pipeline stability: 100% passing rate across supported Python versions before release.
- Validation effectiveness: zero regressions from invalid lattice/coordinate data in acceptance tests.
- Performance goals: >30% reduction in index build time on 10k-structure containers; measurable compression improvements with new algorithms.
- Documentation engagement: increase unique doc visits/downloads (or internal metrics) quarter over quarter.
- Ecosystem adoption: track CLI downloads or container feature usage in downstream projects.

## Immediate Next Steps
1. Confirm desired licensing model with stakeholders and update all metadata accordingly.
2. Bootstrap CI + developer tooling (pre-commit, linting, typing) to enforce code quality automatically.
3. Prioritize container thread-safety refactor and write concurrent access tests as the first functional milestone.
4. Schedule a documentation sprint to unify architecture, binary format, and upgrade guidance ahead of Sphinx rollout.

---

*Document prepared: November 2025*  
*Maintained in `docs/` for iterative updates.*


