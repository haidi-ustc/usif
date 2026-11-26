# Materials Project data

The Materials Project (MP) tooling is a development script in [`scripts/materials_project`](../../scripts/materials_project/README.md), not part of the installed package. Run it from the repository root; it needs `pip install -r scripts/materials_project/requirements.txt` (`monty`, plus `mp-api` for downloads).

## Build a dataset

```bash
python -m scripts.materials_project build tests/fixtures/mp_structures mp.usifc
usif dataset list mp.usifc --prop "band_gap>0.5"
```

`build` reads every `group_*/materials.json` under the source directory and adds one entry per `material_id` to the group `/mp`. New data comes from `python -m scripts.materials_project download --output-dir data/mp` (needs `MP_API_KEY`).

## What a material becomes

- the structure, with per-atom `oxidation_state` and `magmom` (μB) when MP provides them;
- numeric summary fields as queryable properties with MP's units: `band_gap` (eV), `energy_per_atom`, `uncorrected_energy_per_atom`, `formation_energy_per_atom`, `energy_above_hull` (eV/atom), `density` (g/cm^3), `total_magnetization` (μB, whole cell);
- `energy`: the raw DFT total of the cell, `uncorrected_energy_per_atom * natoms` (eV). MP's `energy_per_atom` includes the MP2020 corrections and is kept apart;
- `material_id`, `formula_pretty`, `is_*` flags and `spacegroup_number`/`spacegroup_symbol`.

The [script's README](../../scripts/materials_project/README.md) lists the options and the Python API. Query the result as any other dataset; see [Datasets](datasets.md).
