# Materials Project Data Download

This directory contains the optional live Materials Project downloader used to create local fixture-style datasets for USIF testing and experiments.

## Setup

Install the optional Materials Project dependencies:

```bash
python -m pip install -e ".[mp]"
```

Get an API key from the Materials Project dashboard and prefer the environment variable form so the key is not stored in shell history:

```bash
export MP_API_KEY="your_api_key_here"
```

The CLI still accepts `--api_key` for local interactive use, but the environment variable is safer.

## Usage

Download the default dataset shape:

```bash
python examples/download_mp_data.py
```

Download fewer entries into a custom location:

```bash
python examples/download_mp_data.py \
    --output_dir data/my_mp_structures \
    --total_entries 100 \
    --entries_per_group 25
```

Filter by band gap:

```bash
python examples/download_mp_data.py \
    --min_band_gap 0.5 \
    --max_band_gap 3.0
```

Show CLI help without an API key:

```bash
python examples/download_mp_data.py --help
```

## Output structure

The downloader writes grouped JSON documents. Each group contains one `materials.json` file with a list of Materials Project summary documents:

```text
data/mp_structures/
├── metadata.json
├── group_01/
│   └── materials.json
├── group_02/
│   └── materials.json
└── mp_structures.zip
```

This grouped layout matches the current `usif.integrations.materials_project` API.

## Loading downloaded data

Use `load_mp_group()` to read a group and `convert_mp_to_usif()` to map one Materials Project document into a `USIFStructure`:

```python
from usif.integrations.materials_project import convert_mp_to_usif, load_mp_group

docs = load_mp_group("data/mp_structures/group_01/materials.json")
structure = convert_mp_to_usif(docs[0])
print(structure.formula)
```

To load from the archive created by the downloader:

```python
from usif.integrations.materials_project import load_mp_data_from_archive

groups = load_mp_data_from_archive("data/mp_structures/mp_structures.zip")
print(groups.keys())
```

## Notes

- Live download requires `mp-api` and network access.
- The repository tests use bundled fixtures by default; they do not require a live API key.
- API keys are never required for `--help` or local fixture loading.
