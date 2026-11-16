# USIF documentation

USIF 0.9 is a Python library and a set of file formats for atomistic structures. Start with the
[project README](../README.md) for installation and a first example.

## User guide

| Page | Covers |
|---|---|
| [Quickstart](guide/quickstart.md) | Build, save, read and query structures in five minutes |
| [Structures](guide/structures.md) | The `Structure` and `Cell` model: geometry, equality, derived values |
| [Properties and units](guide/properties.md) | Per-atom arrays and structure properties, schemas, unit spelling and conversion |
| [Records and JSON](guide/records.md) | `.usif` records and their options, identity hashes, JSON documents |
| [Datasets](guide/datasets.md) | `.usifc` datasets: groups, attributes, deduplication, queries, checks, concurrency |
| [Other libraries](guide/libraries.md) | matsimpy, ASE and pymatgen conversion and file formats; writing a backend |
| [Command line](guide/command-line.md) | The `usif` command |
| [Upgrading from 0.8](guide/upgrading.md) | Reading and converting files written by USIF 0.8 and earlier |
| [Materials Project data](guide/materials-project.md) | The `scripts/materials_project` download and dataset tool |
| [Public API](guide/api.md) | Every public name, by module |

Runnable scripts for each topic are in [examples/](../examples/README.md).

## Reference

| Document | Covers |
|---|---|
| [BINARY_FORMAT.md](BINARY_FORMAT.md) | Byte layout of the `.usif` record, format 7 |
| [DATASET_FORMAT.md](DATASET_FORMAT.md) | SQLite schema and semantics of `.usifc` datasets |
| [FORMATS_0_8.md](FORMATS_0_8.md) | Frozen specifications of the USIF 0.8 formats (records 5/6, container v2) |
| [FORMAT_VERSIONING.md](FORMAT_VERSIONING.md) | When the record and dataset versions change |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Packages, layering, data flow and extension points |
| [API_STABILITY.md](API_STABILITY.md) | What is public and how it may change |

## Project

| Document | Covers |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Release notes, including the 0.8 -> 0.9 migration table |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, checks, test layout, guidelines |
| [RELEASE.md](RELEASE.md) | Version policy, release record and release checklist |
