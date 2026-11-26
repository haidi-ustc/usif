# USIF: Universal Structure Interchange Format

USIF stores atomistic structures (crystals and molecules) exactly, compactly and queryably.

- **One simple model.** A `Structure` is columns: atomic numbers, Cartesian positions, an optional
  cell, per-atom arrays and structure properties. Every value carries a dtype and a unit.
- **Exact files.** A `.usif` record holds one structure, bit-for-bit (float64) by default, with a
  checksum and content hashes. Opt-in float32, compression and lossless symmetry reduction make
  it smaller. A `.json` document is the readable alternative.
- **Datasets you can query.** A `.usifc` dataset is an SQLite file of many structures. It stores
  identical content once, organises entries in groups with attributes, and answers indexed
  queries (formula, elements, atom count, property ranges).
- **Works with your tools.** USIF converts to and from matsimpy, ASE and pymatgen objects, reads
  and writes every file format they support, and has a `usif` command line.
- **A data agent you talk to.** Register a group's calculations in one local dataset, then query
  it, create projects and save data into them in plain words. An LLM proposes every change as a
  plan; nothing is written until a person approves it.
- **Small core.** Only numpy, spglib and typer are required; every structure library is optional.

Python 3.10+. Version 0.12.0 (see the [changelog](docs/CHANGELOG.md)). Files written by USIF 0.8 and earlier are still readable (see
[Upgrading from 0.8](#upgrading-from-08)).

## Installation

```bash
pip install usif                  # core
pip install "usif[ase]"           # + ASE: conversion and ASE's file formats
pip install "usif[pymatgen]"      # + pymatgen
pip install "usif[zstd]"          # + zstd record compression
```

| Extra | Installs | For |
|---|---|---|
| `ase` | ase | `usif.convert(..., "ase")` and ASE file formats (POSCAR, extxyz, CIF, ...) |
| `pymatgen` | pymatgen | `usif.convert(..., "pymatgen")` and pymatgen file formats |
| `matsimpy` | matsimpy | the matsimpy backend (not on PyPI: `pip install -e /path/to/matsimpy`) |
| `zstd` | zstandard | `compression="zstd"` |
| `dev` | pytest, black, isort, mypy, bandit, pip-audit, build | development |
| `all` | everything above except matsimpy | |

There is no `mp` extra any more: the Materials Project download script is a development tool in
`scripts/materials_project/`, and its dependencies (mp-api, monty) are in
`scripts/materials_project/requirements.txt`.

## Quickstart

```python
import usif
from usif import Cell, Dataset, Q, Structure

nacl = Structure.from_fractional(
    ["Na", "Cl"],
    [[0, 0, 0], [0.5, 0.5, 0.5]],
    Cell.cubic(5.64),
    properties={"energy": -6.8},          # unit "eV" comes from the default schema
)
nacl.arrays["force"] = [[0, 0, 0.01], [0, 0, -0.01]]   # per-atom, eV/Å

usif.write(nacl, "nacl.usif")             # binary record
assert usif.read("nacl.usif") == nacl     # exact round trip
usif.write(nacl, "nacl.json")             # readable JSON, also exact

with Dataset("data.usifc") as ds:         # SQLite dataset, created if missing
    ds.add(nacl, "nacl", "/salts", attrs={"source": "example"})
    for entry in ds.query(Q.elements("Na") & (Q.prop("energy") < 0)):
        print(entry.path, entry.structure.reduced_formula)   # /salts/nacl NaCl
```

With ASE installed, other formats and objects work the same way:
`usif.read("POSCAR")`, `usif.write(s, "frames.extxyz")`, `usif.convert(atoms)`,
`usif.convert(s, "ase")`.

## Concepts in brief

| Concept | Summary | Guide |
|---|---|---|
| Structure | `Structure(numbers, positions, cell=None, *, pbc, arrays, properties)`. Immutable geometry; exact `==`, tolerant `allclose()`; derived `formula`, `volume`, ... | [structures](docs/guide/structures.md) |
| Properties | `arrays` (per atom) and `properties` (per structure) hold numbers, arrays or JSON, each with a unit. Built-ins such as `energy` (eV), `force` (eV/Å), `stress` (GPa) come from `DEFAULT_SCHEMA`. Stored values are never converted. | [properties](docs/guide/properties.md) |
| Records | `usif.encode(s, compression="zlib", precision="f64", symmetry="off")`. Encoding is deterministic, and `record_hash`/`geometry_hash` identify content. | [records](docs/guide/records.md) |
| Datasets | `Dataset(path)`: `add`, `add_many`, `link`, `query(Q...)`, `count`, groups and attributes, `check`, `compact`. Many readers can work alongside one writer. | [datasets](docs/guide/datasets.md) |
| Data agent | `usif dataset import` and `usif agent ask/chat`: provenance-tracked import, plain-language queries, projects, change plans you approve. | [agent](docs/guide/agent.md) |
| Backends | matsimpy, ASE and pymatgen built in; values convert to each library's units. Third-party backends plug in through the `usif.backends` entry point. | [libraries](docs/guide/libraries.md) |

## Command line

```bash
usif inspect nacl.usif                     # .usif, .json, any backend format or a .usifc
usif convert POSCAR nacl.usif --symmetry auto
usif validate data.usifc --full            # exit code 1 if invalid
usif dataset add data.usifc *.cif --group /cifs
usif dataset list data.usifc --elements Na,Cl --prop 'energy<-1.5'
usif dataset export data.usifc salts.extxyz --group /salts --prop 'energy<-1.5'  # never overwrites without --overwrite
```

See the [command-line guide](docs/guide/command-line.md) for every command and option.

## A local dataset for your group, with an AI agent

Register the calculations scattered across project directories in one searchable dataset, and
work with it in plain words:

```bash
usif dataset import ~/projects/oer group.usifc --group /oer   # VASP dirs, CIF, extxyz, ... + provenance
export DEEPSEEK_API_KEY=...                                   # any OpenAI-compatible LLM; DeepSeek by default
usif agent ask group.usifc "Which Ti oxides do we have, and with which ENCUT?"
usif agent ask group.usifc "Create a project 'stable' and save every Ti oxide below -40 eV into it"
usif agent ask new.usifc "Start a project for the OER work"   # a new dataset, created on approval
usif agent chat group.usifc --allow ~/projects                # "save the new runs in ~/projects/oer into oer"
export USIF_DATASET=$PWD/group.usifc                          # optional default (or [agent] dataset in ~/.usif/config.toml)
usif agent ask "Which projects do we have?"
```

What you can ask for:

- **Query.** Search by formula, elements, atom count, property ranges (`energy < -10`),
  attributes and text in paths, notes and INCAR parameters; list projects and their contents.
- **Create a project.** A project is the group `/projects/<name>` with a description. The dataset
  is created if it does not exist yet.
- **Save into a project.** New files from allowed directories are imported with provenance;
  entries already in the dataset (for example what a search found) are *linked*, so nothing is
  copied.

The agent reads the dataset and your files and proposes changes as a change plan. Nothing is
written until you approve the plan (`[y/N]`; the agent itself can never approve): changes are
applied in one transaction, checked against source-file hashes, and each new entry records the
plan that added it. The agent never writes files either: for an export it gives you the
`usif dataset export` command to run. See the [agent guide](docs/guide/agent.md) and
[`examples/07_agent_projects.py`](examples/07_agent_projects.py), which runs offline with a
scripted model.

## Upgrading from 0.8

0.9.0 is a redesign: the 0.8 API (`USIFStructure`, `USIF`, `StructureContainer`,
`usif.services`, `usif.interop`, `SymmetryPolicy`, `PropertyRegistry`) is replaced. Files from
0.8 and earlier still open. `usif.read()` reads format-5/6 `.usif` records, and version-2
`.usifc` containers are copied into a dataset with `Dataset.import_v2()`; `usif convert
old.usif new.usif` rewrites a record as format 7. The [upgrade guide](docs/guide/upgrading.md) and the migration table in
the [changelog](docs/CHANGELOG.md) map each old call to its replacement.

## Documentation

- [Documentation index](docs/README.md): the user guide, the format specifications, architecture
  and project documents
- [examples/](examples/README.md): runnable scripts, one per topic
- [scripts/](scripts): development scripts (`python -m scripts.benchmark`,
  `python -m scripts.materials_project`, `scripts/check_release_metadata.py`)

## Development

```bash
python -m pip install -e ".[dev,pymatgen,ase]" -r scripts/materials_project/requirements.txt
pytest                      # from the repository root; always tests this checkout
```

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for the checks CI runs, the test layout and the
project's rules, and [RELEASE.md](docs/RELEASE.md) for versioning and releases.

## License

See [LICENSE](LICENSE).
