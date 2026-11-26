# USIF: Universal Structure Interchange Format

USIF stores atomistic structures — crystals and molecules — exactly, compactly and queryably.

```python
import usif

s = usif.read("POSCAR")                    # any ASE, pymatgen or USIF file
usif.write(s, "nacl.usif")                 # one exact, checksummed record
usif.write(s, "frames.extxyz")             # or any format a backend supports
```

## What it does

- **One simple model.** A `Structure` is columns: atomic numbers, Cartesian positions, an optional
  cell, per-atom arrays and structure properties. Every value carries a dtype and a unit.
- **Exact files.** A `.usif` record holds one structure bit-for-bit, with a checksum and content
  hashes. Float32, compression and lossless symmetry reduction are opt-in and make it smaller.
  `.json` is the readable alternative.
- **Datasets you can query.** A `.usifc` dataset is one SQLite file of many structures: identical
  content is stored once, entries live in groups with attributes, and indexed queries answer
  formula, element, size and property-range questions.
- **Works with your tools.** Conversion to and from matsimpy, ASE and pymatgen objects and files,
  plus a `usif` command line.
- **A data agent you talk to.** Import a group's calculations into a local dataset, then query it
  and organise it in plain words. An LLM proposes each change as a plan; nothing is written until
  a person approves it.
- **Small core.** Only numpy, spglib and typer are required; the structure libraries are optional.

## Installation

```bash
pip install usif                  # core, Python 3.10+
pip install "usif[ase]"           # ASE objects and file formats
pip install "usif[pymatgen]"      # pymatgen objects and file formats
pip install "usif[zstd]"          # zstd record compression
pip install "usif[all]"           # ase + pymatgen + zstd
```

The matsimpy backend uses matsimpy installed separately (it is not on PyPI).

## Quickstart

```python
import usif
from usif import Cell, Dataset, Q, Structure

nacl = Structure.from_fractional(
    ["Na", "Cl"],
    [[0, 0, 0], [0.5, 0.5, 0.5]],
    Cell.cubic(5.64),
    properties={"energy": -6.8},           # unit "eV" comes from the default schema
)
nacl.arrays["force"] = [[0, 0, 0.01], [0, 0, -0.01]]   # per atom, eV/Å

usif.write(nacl, "nacl.usif")              # binary record
assert usif.read("nacl.usif") == nacl      # exact round trip
usif.write(nacl, "nacl.json")              # readable JSON, also exact

with Dataset("data.usifc") as ds:          # SQLite dataset, created if missing
    ds.add(nacl, "nacl", "/salts", attrs={"source": "example"})
    for entry in ds.query(Q.elements("Na") & (Q.prop("energy") < 0)):
        print(entry.path, entry.structure.reduced_formula)   # /salts/nacl NaCl
```

## Concepts

| Concept | Summary | Guide |
|---|---|---|
| Structure | `Structure(numbers, positions, cell=None, *, pbc, arrays, properties)`. Immutable geometry, exact `==`, tolerant `allclose()`, derived `formula`, `volume`, ... | [structures](docs/guide/structures.md) |
| Properties | `arrays` (per atom) and `properties` (per structure) hold numbers, arrays or JSON, each with a unit. Built-ins such as `energy` (eV), `force` (eV/Å) and `stress` (GPa) come from `DEFAULT_SCHEMA`; stored values are never converted. | [properties](docs/guide/properties.md) |
| Records | `usif.encode(s, compression="zlib", precision="f64", symmetry="off")` is deterministic; `record_hash` and `geometry_hash` identify content. | [records](docs/guide/records.md) |
| Datasets | `Dataset(path)`: `add`, `add_many`, `link`, `query(Q...)`, `count`, groups and attributes, `check`, `compact`. Many readers alongside one writer. | [datasets](docs/guide/datasets.md) |
| Backends | matsimpy, ASE and pymatgen built in; values convert to each library's units. Third-party backends plug in through the `usif.backends` entry point. | [libraries](docs/guide/libraries.md) |

## Command line

```bash
usif inspect nacl.usif                     # .usif, .json, a .usifc or a backend format
usif convert POSCAR nacl.usif --symmetry auto
usif validate data.usifc --full            # exit code 1 if invalid
usif dataset add data.usifc *.cif --group /cifs
usif dataset list data.usifc --elements Na,Cl --prop 'energy<-1.5'
usif dataset export data.usifc salts.extxyz --group /salts --prop 'energy<-1.5'
```

`export` never overwrites an existing file without `--overwrite`. The
[command-line guide](docs/guide/command-line.md) documents every command and option.

## Datasets and the data agent

```bash
usif dataset import ~/projects/oer group.usifc --group /oer   # VASP dirs, CIF, extxyz, ... + provenance
export DEEPSEEK_API_KEY=...                                   # any OpenAI-compatible model
usif agent ask group.usifc "Which Ti oxides do we have, and with which ENCUT?"
usif agent ask group.usifc "Create a project 'stable' and save every Ti oxide below -40 eV into it"
usif agent chat group.usifc --allow ~/projects                # follow-up questions and imports
```

- **Ask in plain words.** Formula, elements, atom count, property ranges, attributes, text in
  paths and INCAR parameters.
- **Create projects.** A project is the group `/projects/<name>` with a description; the dataset is
  created if it does not exist yet.
- **Save data.** New files from allowed directories are imported with provenance; entries already
  in the dataset are linked, so nothing is copied.

The agent reads and proposes; you approve the plan (`[y/N]`) and the changes are applied in one
transaction, checked against source-file hashes. It never writes files: to export, it gives you the
`usif dataset export` command. See the [agent guide](docs/guide/agent.md) and
[`examples/07_agent_projects.py`](examples/07_agent_projects.py), which runs offline with a
scripted model.

## Documentation

- [Documentation index](docs/README.md): the user guide, format specifications and architecture
- [examples/](examples/README.md): runnable scripts, one per topic
- [scripts/](scripts): development tools (`python -m scripts.benchmark`,
  `python -m scripts.materials_project`)

## Development

```bash
python -m pip install -e ".[dev,pymatgen,ase]" -r scripts/materials_project/requirements.txt
pytest                                     # from the repository root
```

[CONTRIBUTING.md](docs/CONTRIBUTING.md) lists the checks CI runs and the test layout;
[RELEASE.md](docs/RELEASE.md) covers versioning and releases.

## License

See [LICENSE](LICENSE).
