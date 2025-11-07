# Materials Project Data Download

This directory contains scripts for downloading high-quality crystal structures from the Materials Project for USIF testing.

## Setup

### 1. Install Dependencies

```bash
pip install pymatgen mp-api
```

### 2. Get Materials Project API Key

1. Go to https://materialsproject.org/api
2. Sign up for a free account
3. Get your API key from the dashboard

### 3. Set API Key (Optional)

You can set the API key as an environment variable:

```bash
export MP_API_KEY="your_api_key_here"
```

Or pass it directly to the script with `--api_key` argument.

## Usage

### Basic Usage

Download 1000 structures (100 per group, 10 groups) with default quality filters:

```bash
python examples/download_mp_data.py --api_key YOUR_API_KEY
```

### Custom Output Directory

```bash
python examples/download_mp_data.py \
    --api_key YOUR_API_KEY \
    --output_dir data/my_test_structures
```

### Filter by Band Gap

Download only semiconductors with band gap between 0.5 and 3.0 eV:

```bash
python examples/download_mp_data.py \
    --api_key YOUR_API_KEY \
    --min_band_gap 0.5 \
    --max_band_gap 3.0
```

### Custom Number of Entries

```bash
python examples/download_mp_data.py \
    --api_key YOUR_API_KEY \
    --total_entries 500 \
    --entries_per_group 50
```

## Output Structure

The script creates the following directory structure:

```
data/mp_structures/
├── group_01/
│   ├── mp-12345.json
│   ├── mp-12346.json
│   └── ...
├── group_02/
│   ├── mp-12347.json
│   └── ...
├── ...
└── metadata.json
```

## Data Format

Each structure is saved as a JSON file in pymatgen format with the following structure:

```json
{
  "@module": "pymatgen.core.structure",
  "@class": "Structure",
  "lattice": {...},
  "sites": [...],
  "properties": {
    "material_id": "mp-12345",
    "formation_energy_per_atom": -2.5,
    "formation_energy": -25.0,
    "energy_per_atom": -10.5,
    "energy": -105.0,
    "band_gap": 1.2,
    "volume": 100.5,
    "density": 5.2,
    "total_magnetization": 0.0,
    "nsites": 10,
    "nelements": 2,
    "elements": ["Si", "O"],
    "spacegroup": 227,
    "crystal_system": "cubic",
    "is_magnetic": false,
    "is_metal": false,
    "is_gap_direct": true
  },
  "material_id": "mp-12345"
}
```

## Properties Included

The script downloads the following basic properties for each structure:

- **Energy properties**: `formation_energy_per_atom`, `formation_energy`, `energy_per_atom`, `energy`
- **Electronic properties**: `band_gap`, `is_metal`, `is_gap_direct`
- **Structural properties**: `volume`, `density`, `spacegroup`, `crystal_system`
- **Composition properties**: `nsites`, `nelements`, `elements`
- **Magnetic properties**: `total_magnetization`, `is_magnetic`
- **Identifier**: `material_id`

## Quality Filters

By default, the script applies the following quality filters:

- **Energy above hull**: ≤ 0.1 eV (stable or near-stable structures)
- **Structure size**: ≤ 200 sites (reasonable for testing)
- **Band gap**: Optional filters via `--min_band_gap` and `--max_band_gap`

## Loading Structures

You can load structures using the helper function:

```python
from pathlib import Path
from examples.download_mp_data import load_structure

# Load a structure
structure, properties = load_structure(Path("data/mp_structures/group_01/mp-12345.json"))

# Use with USIF
from usif import USIFStructure

usif_structure = USIFStructure.from_pymatgen(
    structure,
    energy=properties.get("energy"),
    # ... other properties
)
```

## Using with USIF Testing

Example script to convert MP structures to USIF format:

```python
from pathlib import Path
from usif import USIFStructure
from examples.download_mp_data import load_structure

# Load all structures from a group
group_dir = Path("data/mp_structures/group_01")
usif_structures = []

for json_file in group_dir.glob("*.json"):
    structure, properties = load_structure(json_file)
    
    # Convert to USIF with properties
    usif_struct = USIFStructure.from_pymatgen(
        structure,
        energy=properties.get("energy"),
        # Add other properties as needed
    )
    
    usif_structures.append(usif_struct)

# Save or use for testing
```

## Notes

- The Materials Project API has rate limits for free accounts
- Downloading 1000 structures may take 10-30 minutes depending on API response time
- Structures are saved in pymatgen JSON format for easy loading
- All properties are included in the JSON file for later use
- The script automatically organizes structures into groups for easier management

## Troubleshooting

### API Key Issues

If you get authentication errors:
1. Verify your API key is correct
2. Check that your API key is active on materialsproject.org
3. Free accounts have rate limits - wait a few minutes if you hit limits

### Import Errors

If you get import errors:
```bash
pip install --upgrade pymatgen mp-api
```

### No Structures Found

If no structures match your filters:
- Try relaxing `--e_above_hull_max` (e.g., 0.2 or 0.5)
- Remove band gap filters
- Check that your API key has access to the data

