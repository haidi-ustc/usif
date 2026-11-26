# USIF examples

Run the examples from the repository root, with USIF installed (`pip install -e .`) or with the repository on `PYTHONPATH`. Each script works in a temporary directory and leaves no files behind. `tests/examples/test_examples.py` runs all of them.

| Script | Shows | Needs |
|---|---|---|
| `quickstart.py` | Build a structure, write and read a `.usif` file, store and query it in a dataset | core |
| `01_structures_and_records.py` | Properties with units, per-atom arrays, record options (compression, precision, symmetry), geometry and record hashes, exact JSON round trip | core |
| `02_dataset_workflow.py` | Datasets: `add_many`, groups and attributes, deduplication, `link` (one record in two groups), `Q` queries, `check`, `compact`, read-only access | core |
| `03_library_conversion.py` | Round trips through matsimpy, ASE and pymatgen objects; writing and reading extxyz | each installed backend (missing ones are skipped) |
| `04_upgrade_0_8_files.py` | Reading a format-5 record, listing a v2 container, importing it into a dataset | core (uses `tests/fixtures/`) |
| `05_cli_workflow.py` | The `usif` command line, run through `usif.cli.main`: inspect, convert, `dataset add`, `dataset import` with a saved change plan, `agent show`, `dataset list`, `validate` | core |
| `06_local_dataset.py` | A group's local dataset: scan a project directory, review and apply the change plan, search by properties and provenance | core |
| `07_agent_projects.py` | Projects in plain words: the data agent (a scripted model, no API key) creates a project, saves search results into it as links, and answers a question about it; the plan is applied after approval | core |

```bash
python examples/quickstart.py
python examples/02_dataset_workflow.py
```

Benchmarks and Materials Project data are development scripts in [`scripts/`](../scripts):
`python -m scripts.benchmark` and `python -m scripts.materials_project --help`
(see [its README](../scripts/materials_project/README.md)).

The [user guide](../docs/README.md) explains each topic; every page points to its example.
