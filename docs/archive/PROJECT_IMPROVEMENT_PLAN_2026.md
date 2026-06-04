# USIF Modernization Roadmap 2026

## Executive Summary
The USIF codebase remains a strong foundation for structure interchange, yet several architectural and process issues now limit scalability, safety, and adoption. This roadmap captures a deeper scan of the repository (November 2025) and consolidates technical debt, quality gaps, and strategic growth opportunities. The goal is to harden core components—particularly indexing, validation, and packaging—while elevating developer experience and user-facing capabilities.

## 1. Technical Audit Highlights

- **Container subsystem** (`usif/container.py`) still lacks full thread safety; index mutations are unguarded and secondary indexes only cover a 10-element window.
- **Binary encoder** (`usif/encoder.py`) duplicates serialization logic for hashing and lacks a formal migration path for `FORMAT_VERSION`.
- **Converters** (`usif/converter.py`) accept property arrays without shape validation and silently downgrade symmetry analysis.
- **Structure model** (`usif/structures/structure.py`) validates structural presence but not geometric validity (lattice determinants, fractional bounds, formula consistency).
- **Packaging metadata** (`pyproject.toml`, `LICENSE`, README) remains inconsistent with the stated non-commercial license.
- **Tooling/CI**: No automated linting, type checking, or packaging steps; pre-commit hooks are absent; no artifacts published on releases.
- **Documentation**: Rich Markdown content exists, but there is no generated API reference, upgrade guide, or consolidated architecture documentation.
- **Testing gaps**: Missing concurrency tests, corruption recovery scenarios, property shape edge cases, and performance regression tracking.

## 2. Improvement Themes & Recommendations

### 2.1 Data Integrity & Validation
- Harden `USIFStructure` validation: enforce positive lattice volume, reasonable angles, and fractional coordinate bounds; auto-generate formulae and cross-check composition.
- Enforce property array shapes in converters; raise descriptive `ValidationError` when mismatches occur.
- Introduce schema migration hooks at decode time to future-proof `FORMAT_VERSION` evolution.

### 2.2 Concurrency & Indexing
- Wrap all container index mutations (`_update_secondary_indexes`, `_write_enhanced_index`, `_build_secondary_indexes`) with locks; audit cache and index state for thread-safe access.
- Replace the 10-structure secondary index cap with full indexing or a configurable limit; provide lazy initialization for large datasets.
- Track cache hit/miss counts and surface in `stats()` for observability.

### 2.3 Packaging & Release Engineering
- Align license declarations and publish a clear commercial licensing note.
- Adopt a modern build backend (`hatchling` or PEP 517-compliant setuptools config) and publish reproducible wheels/sdist.
- Implement CI pipelines (GitHub Actions) covering lint (`ruff`), format (`black`), type check (`mypy`), tests (`pytest`), and packaging.
- Introduce dependency update automation (Dependabot/Renovate) with upper bounds for critical libraries (`pymatgen`, `numpy`).

### 2.4 Developer Experience
- Introduce `pre-commit` with black/ruff/isort/mypy hooks; document workflow in `CONTRIBUTING.md`.
- Generate Sphinx documentation site combining architecture overview, binary specification, API reference, and migration guides.
- Provide example notebooks and CLI utilities (`usif-cli`) for common operations (convert, inspect, benchmark).
- Standardize logging (structured JSON optional) and error message formats for consistent diagnostics.

### 2.5 Testing & Quality Assurance
- Add multithreaded tests for `StructureContainer`; include stress tests for large insert/query workloads.
- Extend tests for corrupted file recovery, property validation edge cases, and multi-format roundtrips.
- Introduce performance benchmarks comparing compression algorithms and indexing strategies.
- Consider fuzz testing for binary decoder and property serializer.

## 3. Phased Roadmap

### Phase 0 (0-1 month): Alignment & Tooling
- Resolve license mismatch; update `LICENSE`, README, and `pyproject.toml`.
- Bootstrap CI (GitHub Actions) with lint/test/build stages; add coverage reporting.
- Introduce `pre-commit` and developer setup guide; enforce consistent formatting.
- Audit and clean packaging metadata; add `pyproject-build` and `twine check` to CI.

### Phase 1 (1-3 months): Core Safety Improvements
- Implement full locking strategy for container indexes; add regression tests.
- Expand secondary indexes and cache stats; support configurable index depth.
- Harden structure and converter validation paths; update tests accordingly.
- Extract shared serialization utilities to eliminate hash vs. encode drift.

### Phase 2 (3-6 months): Performance & Documentation
- Add lazy-loading or streaming APIs for large containers; benchmark memory usage.
- Provide alternative compression algorithms (LZMA, Zstandard) behind feature flags.
- Launch Sphinx-generated documentation with architecture diagrams and API reference.
- Publish CLI utilities and example notebooks demonstrating key workflows.

### Phase 3 (6-12 months): Ecosystem Expansion
- Implement advanced query capabilities (composition filters, property ranges, similarity search).
- Introduce telemetry hooks (opt-in) for monitoring usage patterns.
- Engage with community via beta releases; collect feedback for future iterations.
- Maintain quarterly roadmap reviews and publish release notes/changelog.

## 4. Success Metrics
- **Reliability**: Zero detected corruption or crashes from concurrent access after Phase 1.
- **Validation**: Automated tests covering lattice/coordinate/array validation reach >95% coverage.
- **Performance**: Secondary index rebuild time reduced by >30% on 10k-structure datasets; optional compression shows >20% size reduction vs. baseline.
- **Documentation**: Sphinx docs deployed; upgrade guide referenced in each release.
- **Developer Adoption**: Pre-commit adoption across contributors; CI remains green on all supported Python versions.

## 5. Immediate Next Steps
1. Confirm licensing strategy and update metadata files to eliminate conflicts.
2. Draft CI workflows and add essential QA tooling (`ruff`, `mypy`, `pytest`, `build`).
3. Scope container locking refactor; design tests to reproduce current concurrency issues.
4. Schedule documentation sprint to consolidate architecture and format specifications for Sphinx migration.

---
*Maintained by: USIF Engineering Team*  
*Revision: November 2025*  
*Stored in `docs/PROJECT_IMPROVEMENT_PLAN_2026.md` for ongoing updates*

