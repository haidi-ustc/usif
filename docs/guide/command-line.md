# Command line

Installing USIF provides the `usif` command. From Python, `usif.cli.main(argv)` runs the same commands and returns the exit code; [`examples/05_cli_workflow.py`](../../examples/05_cli_workflow.py) does this.

| Command | Purpose |
|---|---|
| `usif version [--json]` | Package version, release record, record format and dataset schema versions. |
| `usif --version` | Package version only. |
| `usif inspect PATH [--json]` | Summary of a structure file (formula, cell, property units, and for `.usif` the record format, hashes and compression) or of a `.usifc` dataset (counts, groups, metadata). |
| `usif convert INPUT OUTPUT` | Convert one structure between any supported formats. Options for `.usif` output: `--compression`, `--precision`, `--symmetry`. For backend formats: `--backend`, `--format`. |
| `usif validate PATH [--full] [--json]` | Decode a structure file, or check a dataset (`--full` decodes and re-hashes every record). Exit code 1 if invalid. |
| `usif upgrade SOURCE TARGET [--symmetry auto]` | Rewrite a format-5/6 `.usif` record or a v2 `.usifc` container in the current format (see [Upgrading](upgrading.md)). |
| `usif dataset add DATASET FILES... [--group G] [--symmetry] [--compression]` | Add every frame of each file. Entry names are file stems (`stem-0`, `stem-1`, ... for multi-frame files), existing names are overwritten, and each entry gets the attribute `source` (the file name). |
| `usif dataset list DATASET [filters] [--limit N] [--json]` | List matching entries. Filters: `--group`, `--formula`, `--chemsys`, `--elements Fe,O`, `--max-atoms`, `--prop 'energy<-1.5'` (repeatable). |
| `usif dataset export DATASET OUTPUT [--entry KEY]... [filters] [--limit N] [--format F] [--overwrite]` | Write the selected entries to one file, in dataset order: the `--entry` paths (`/group/name` or record hash, repeatable), or every entry matching the filters of `dataset list` (all entries if neither is given). One structure can go to any format, including `.usif` and `.json`; several need a multi-frame format such as `.extxyz`. An existing `OUTPUT` is refused unless `--overwrite` is given (it is then replaced only after the new file is complete), and nothing is written when no entry matches. See [Exporting](datasets.md#exporting). |
| `usif dataset compact DATASET` | Drop unreferenced records and reclaim space. |
| `usif dataset import SOURCE DATASET [--group G] [--all-frames] [--update] [--symmetry] [--plan-out FILE] [-y]` | Scan a project directory for calculations and structure files and register them with provenance attributes. Shows the change plan and asks before applying; `--yes` applies directly. See [Data agent](agent.md). |
| `usif agent ask DATASET REQUEST [--allow DIR] [--plan-out FILE] [--model] [--base-url]` | Ask the LLM agent a question or give it an instruction ("which runs used ENCUT 520?", "create a project oer and save the Ti oxides with a gap above 1 eV into it"). `DATASET` may be a new file: an approved plan creates it. Proposed changes are shown as a plan and need your approval. |
| `usif agent chat DATASET [--allow DIR]` | Interactive agent session (`/plan`, `/apply`, `/save FILE`, `/discard`, `/quit`). |
| `usif agent show PLAN [--json]` | Print a saved change plan. |
| `usif agent apply PLAN [-y]` | Apply a reviewed plan in one transaction (asks first; `--yes` when not on a terminal). |
| `usif agent plans [--applied] [--json]` | Plans waiting for review in `~/.usif/plans`, or the journal of applied plans. |
| `usif agent config [--json]` | The LLM settings in effect (the key is only reported as set or not). |

Every command and group accepts `-h`/`--help`; a bare group (`usif dataset`, `usif agent`) prints its help. USIF errors are printed as `usif: error: ...` with exit code 2.

## Example session

```bash
usif convert POSCAR nacl.usif --symmetry auto
usif inspect nacl.usif
usif convert nacl.usif nacl.json
usif dataset add data.usifc nacl.usif --group /salts
usif dataset list data.usifc --formula NaCl
usif dataset list data.usifc --prop 'energy<-1.5' --json
usif dataset export data.usifc nacl.cif --entry /salts/nacl
usif dataset export data.usifc salts.extxyz --group /salts --prop 'energy<-1.5'
usif validate data.usifc --full
```

Quote `--prop` filters so the shell does not treat `<` and `>` as redirections.

`usif dataset export` before 0.12 took one entry as a positional argument (`export DATASET KEY
OUTPUT`); it is now `export DATASET OUTPUT --entry KEY`. [`examples/08_export_query.py`](../../examples/08_export_query.py)
runs the export rules.
