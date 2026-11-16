# Materials Project data

`scripts/materials_project` downloads Materials Project summary documents (structures plus fields
such as band gap and formation energy) with mp-api, saves them as JSON, and converts them into a
USIF dataset. It is a development script, not part of the installed `usif` package. The bundled
fixtures in `tests/fixtures/mp_structures` have the same layout as a download.

## Setup

Run from the repository root:

```bash
python -m pip install -e ".[mp]"          # monty and mp-api
export MP_API_KEY="your_api_key_here"
```

Get the API key from the Materials Project dashboard. `--api-key KEY` also works, but the
environment variable keeps the key out of your shell history. `--help` needs neither.

## Usage

```bash
python -m scripts.materials_project download --output-dir data/mp_structures
python -m scripts.materials_project download --output-dir data/mp_small --total-entries 100 --entries-per-group 25
python -m scripts.materials_project build data/mp_structures mp.usifc --group /mp
python -m scripts.materials_project --help
```

`download` options:

| Option | Default | Meaning |
|---|---|---|
| `--api-key` | `MP_API_KEY` | Materials Project API key |
| `--output-dir` | a new temporary directory | Where to write the data |
| `--total-entries` | 1000 | Stop after this many documents |
| `--entries-per-group` | 100 | Documents per query group |
| `--e-above-hull-max` | 0.1 | Skip materials further above the hull (eV/atom) |
| `--min-band-gap`, `--max-band-gap` | group presets | Override the band-gap range of every group (eV) |
| `--rate-limit` | 2.0 | Seconds to wait between groups |
| `--zip/--no-zip` | `--zip` | Also create a zip archive |

The query groups are fixed chemical systems (Si-Ge, Ga-As, In-P, C-N, Li-Fe-P, Na-Cl, Mg-Si, B-N,
Cu-S, and Al-Si-N), defined in `scripts/materials_project/query.py`.

`build SOURCE TARGET` reads every `group_*/materials.json` under `SOURCE` and adds one entry per
`material_id` to the dataset `TARGET` (`--group`, default `/mp`; `--symmetry off|auto`).

## Output

```text
data/mp_structures/
├── metadata.json
├── group_01/
│   └── materials.json
├── group_02/
│   └── materials.json
└── ...
data/mp_structures.zip          # next to the directory, unless --no-zip
```

Each `materials.json` is a list of summary documents written with monty. Groups whose query returns nothing are not written, so the numbering can have gaps.

## What a material becomes

`convert_mp_to_usif(doc)` (in `scripts/materials_project/mapper.py`) accepts a dict or an mp-api
document and returns a `usif.Structure`:

- `structure`: a pymatgen `Structure.as_dict()` document is parsed without pymatgen; disordered
  sites raise `ValidationError`. Oxidation states become the per-atom `oxidation_state` array; site
  properties `magmom`, `forces`, `charge`, `velocities` become `magmom` (μB), `force`, `charge`,
  `velocity`.
- Numeric fields become scalar properties with MP's units, so datasets can filter on them
  (`Q.prop("band_gap") > 1`): `band_gap` (eV), `energy_per_atom`, `uncorrected_energy_per_atom`,
  `formation_energy_per_atom`, `energy_above_hull` (eV/atom), `density` (g/cm^3),
  `total_magnetization` (μB, whole cell).
- `energy` is the raw DFT total energy of the cell, `uncorrected_energy_per_atom * natoms` (eV).
  MP's `energy_per_atom` includes the MP2020 compatibility corrections, so it is kept only as
  `energy_per_atom`. Documents without `uncorrected_energy_per_atom` (such as the bundled fixtures,
  which were downloaded before the field was requested) get no `energy`.
- `material_id`, `formula_pretty`, `is_magnetic`, `is_metal`, `is_stable`, `is_gap_direct`, and
  `spacegroup_number`/`spacegroup_symbol` from `symmetry` are stored as properties too.

From Python (repository root on `sys.path`):

```python
from pathlib import Path
from usif import Dataset, Q
from scripts.materials_project import convert_mp_to_usif, load_mp_group

data = Path("tests/fixtures/mp_structures")
docs = [doc for path in sorted(data.glob("group_*/materials.json")) for doc in load_mp_group(path)]
with Dataset("mp.usifc", "w") as ds:
    ds.add_many((convert_mp_to_usif(d) for d in docs), "/mp",
                names=[str(d["material_id"]) for d in docs])
    print([e.name for e in ds.query(Q.prop("band_gap") > 0.5)])
```

To unpack an archive, `load_mp_data_from_archive("data/mp_structures.zip")` extracts it (with size
and path checks) next to the zip file, or into `extract_to`, and returns the directory path.

Set `MP_DATA_DIR` to a downloaded directory to run the Materials Project tests against it instead
of the bundled fixtures.
