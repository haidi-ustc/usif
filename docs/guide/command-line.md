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
| `usif dataset export DATASET KEY OUTPUT` | Write one entry (path `/group/name` or record hash) to a file. |
| `usif dataset compact DATASET` | Drop unreferenced records and reclaim space. |

USIF errors are printed as `usif: error: ...` with exit code 2.

## Example session

```bash
usif convert POSCAR nacl.usif --symmetry auto
usif inspect nacl.usif
usif convert nacl.usif nacl.json
usif dataset add data.usifc nacl.usif --group /salts
usif dataset list data.usifc --formula NaCl
usif dataset list data.usifc --prop 'energy<-1.5' --json
usif dataset export data.usifc /salts/nacl nacl.cif
usif validate data.usifc --full
```

Quote `--prop` filters so the shell does not treat `<` and `>` as redirections.
