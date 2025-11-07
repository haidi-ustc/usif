# USIF (Universal Structure Interchange Format) v4.0

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Unified format for crystals and molecules with intelligent compression**

USIF is a next-generation file format designed for storing and exchanging atomic structure data with unprecedented efficiency and flexibility. It provides a unified interface for both periodic (crystals) and non-periodic (molecules) structures with intelligent compression capabilities.

## Features

- **Unified Structure Support**: Crystals and molecules with seamless conversion
- **Intelligent Compression**: 4-6x compression vs traditional formats
- **Automatic Symmetry Analysis**: Automatic Wyckoff site extraction from pymatgen structures
- **Modular Property System**: Type-safe properties with units and validation
- **HDF5-like Container**: Hierarchical organization with groups and attributes
- **Easy File I/O**: Simple save/load methods with automatic format detection
- **Materials Project Integration**: Download and convert MP data for testing and benchmarking

## Installation

```bash
# Basic installation (includes pymatgen as required dependency)
pip install -e .

# Development installation with all dependencies
pip install -e ".[all]"
```

**Requirements:**
- Python 3.8+
- pymatgen (required for symmetry analysis and structure conversion)
- numpy
- monty (for serialization)
- ase (optional, for ASE Atoms support - install with: `pip install ase`)

## Quick Start

### High-Level Interface (Recommended)

The easiest way to create USIF structures is using the high-level `from_source()` method, which supports multiple input types:

```python
from usif import USIFStructure

# From file (auto-detects format: CIF, POSCAR, XYZ, etc.)
usif_struct = USIFStructure.from_source(
    "structure.cif",
    energy=-10.5,      # Built-in property
    volume=179.4,      # Built-in property
    calculator="VASP"  # Custom property (stored in structure_properties.custom)
)

# From pymatgen Structure or Molecule object
from pymatgen.core import Structure, Lattice
import numpy as np

# Create a pymatgen structure (or load from file)
lattice = Lattice.cubic(5.64)
species = ["Na", "Cl"]
coords = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]
pmg_struct = Structure(lattice, species, coords)
# Or: pmg_struct = Structure.from_file("structure.cif")

# Define properties
forces_array = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])  # Nx3 array for N atoms
stress_tensor = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])  # 3x3 tensor

usif_struct = USIFStructure.from_source(
    pmg_struct,
    energy=-10.5,           # Built-in property
    forces=forces_array,     # Atomic property
    stress=stress_tensor     # Built-in property
)

# From ASE Atoms object
from ase import Atoms
ase_atoms = Atoms('H2O', positions=[[0, 0, 0], [0.95, 0, 0], [0.95, 0.95, 0]])
usif_struct = USIFStructure.from_source(
    ase_atoms,
    energy=-10.5,           # Built-in property
    calculator="VASP"       # Custom property (stored in structure_properties.custom)
)

# Save directly to .usif file
usif_struct.save("structure.usif")

# Or use the to() method (similar to pymatgen)
usif_struct.to("structure.usif")  # Auto-detects USIF format from extension
usif_struct.to("structure.cif")  # Auto-detects CIF format from extension
usif_struct.to("structure.cif", "cif")  # Explicit format specification
pmg_struct = usif_struct.to(fmt="pymatgen")  # Convert to pymatgen (returns object)
ase_atoms = usif_struct.to(fmt="ase")  # Convert to ASE (returns object)
```

### Creating Structures from Pymatgen (Alternative)

For direct pymatgen conversion, you can also use the `from_pymatgen()` method:

```python
from pymatgen.core import Structure
from usif import USIFStructure

# Load from CIF file
pmg_struct = Structure.from_file("structure.cif")

# Convert to USIF with automatic Wyckoff site extraction
# Built-in properties: energy, stress, volume, pressure, temperature
# Additional kwargs are stored as custom properties
usif_struct = USIFStructure.from_pymatgen(
    pmg_struct,
    energy=-10.5,           # Built-in property
    volume=179.4,           # Built-in property
    calculator="VASP"       # Custom property (stored in structure_properties.custom)
)

# Save directly to .usif file
usif_struct.save("structure.usif")
```

### Manual Structure Creation

For more control, you can create structures manually:

```python
from usif import USIFStructure, StructureType, StorageMode
from usif import WyckoffSite, StructureProperties
import numpy as np

# Create a simple NaCl crystal
lattice_matrix = np.array([
    [5.64, 0.0, 0.0],
    [0.0, 5.64, 0.0],
    [0.0, 0.0, 5.64]
])

wyckoff_sites = [
    WyckoffSite(atomic_number=11, multiplicity=4, coords=(0.0, 0.0, 0.0)),  # Na
    WyckoffSite(atomic_number=17, multiplicity=4, coords=(0.5, 0.5, 0.5))   # Cl
]

structure_props = StructureProperties(
    energy=-10.5,
    volume=179.4,
    custom={"calculator": "VASP"}  # Custom properties dictionary
)

structure = USIFStructure(
    structure_type=StructureType.CRYSTAL,
    storage_mode=StorageMode.SYMMETRIC,
    lattice_matrix=lattice_matrix,
    spacegroup=225,
    wyckoff_sites=wyckoff_sites,
    structure_properties=structure_props,
    formula="NaCl"
)
```

### File I/O and Format Conversion

USIF structures support convenient save/load and format conversion:

```python
# Save to .usif format (uses encoder)
usif_struct.save("structure.usif")

# Save to JSON format (human-readable)
usif_struct.save("structure.json")

# Load from file (auto-detects format)
loaded = USIFStructure.load("structure.usif")

# Convert to various formats using to() method (auto-detects from extension)
usif_struct.to("output.usif")  # Save to USIF (auto-detected)
usif_struct.to("output.cif")  # Export to CIF (auto-detected)
usif_struct.to("output.poscar")  # Export to POSCAR (auto-detected)
usif_struct.to("output.xyz")  # Export to XYZ (auto-detected)

# Explicit format specification
usif_struct.to("output.cif", "cif")  # Explicit format

# Convert to objects (no filename needed)
pmg_struct = usif_struct.to(fmt="pymatgen")  # Get pymatgen Structure/Molecule
ase_atoms = usif_struct.to(fmt="ase")  # Get ASE Atoms object
pmg_struct2 = usif_struct.to()  # Defaults to pymatgen if no args
```

### Using the Encoder Directly

For more control over encoding/decoding:

```python
from usif import USIF, CompressionType

# Create encoder
encoder = USIF(compression=CompressionType.GZIP)

# Encode structure
usif_data = encoder.encode(structure)
print(f"Encoded size: {len(usif_data)} bytes")
print(f"Structure hash: {encoder.get_structure_hash(structure)}")

# Decode back
decoded_structure, hash_value = encoder.decode(usif_data)
```

### Structure Container (HDF5-like)

Store multiple structures with hierarchical organization:

```python
from usif import StructureContainer

# Create container (can use .usif or .usifc suffix)
with StructureContainer("structures.usifc", mode='w') as container:
    # Add structures with names and groups
    hash1 = container.add(
        structure1, 
        name="NaCl_001",
        group="/materials/crystals",
        attributes={"author": "John Doe", "date": "2024-01-01"}
    )
    
    hash2 = container.add(
        structure2,
        name="H2O_001",
        group="/materials/molecules"
    )
    
    # Set group attributes
    container.set_group_attribute("/materials", "description", "Material database")
    
    # Query structures
    results = container.query(formula="NaCl", group="/materials/crystals")
    
    # Get statistics
    stats = container.stats()
    print(f"Total structures: {stats['total_structures']}")

# Read from container
with StructureContainer("structures.usifc", mode='r') as container:
    # Get structure by hash or name
    structure = container.get(hash1)  # or container.get("NaCl_001")
    attrs = container.get_structure_attributes(hash1)
```

## Materials Project Data Integration

USIF includes utilities for downloading and working with Materials Project data:

### Downloading MP Data

```python
from usif.utils import download_mp_data

# Download MP structures for testing
stats = download_mp_data(
    api_key="YOUR_MP_API_KEY",
    output_dir="tests/data/mp_structures",
    total_entries=1000,
    entries_per_group=100,
    e_above_hull_max=0.1,
    create_zip=True  # Creates zip archive for easy sharing
)

print(f"Downloaded {stats['total_downloaded']} structures")
print(f"Zip archive: {stats.get('zip_file')}")
```

Or use the command-line script:

```bash
# Set API key
export MP_API_KEY=your_key_here

# Download data
python examples/download_mp_data.py --total_entries 1000

# Or with custom options
python examples/download_mp_data.py \
    --total_entries 500 \
    --entries_per_group 50 \
    --e_above_hull_max 0.1 \
    --min_band_gap 0.5 \
    --max_band_gap 3.0
```

### Converting MP Data to USIF

```python
from usif.utils import load_mp_group, convert_mp_to_usif

# Load MP data from downloaded files
docs = load_mp_group("tests/data/mp_structures/group_01/materials.json")

# Convert to USIF structures
for doc in docs:
    usif_struct = convert_mp_to_usif(doc)
    
    # Access properties
    print(f"Material: {usif_struct.structure_properties.custom['material_id']}")
    print(f"Formula: {usif_struct.formula}")
    print(f"Energy: {usif_struct.structure_properties.energy} eV")
    print(f"Volume: {usif_struct.structure_properties.volume} Å³")
    print(f"Band gap: {usif_struct.structure_properties.custom.get('band_gap')} eV")
    
    # Save to USIF format
    usif_struct.save(f"{doc['material_id']}.usif")
```

### Loading from Zip Archive

```python
from usif.utils import load_mp_data_from_archive

# Extract and load from zip
extracted_dir = load_mp_data_from_archive(
    "tests/data/mp_structures.zip",
    extract_to="tests/data/mp_extracted"
)

# Then load groups as usual
docs = load_mp_group(f"{extracted_dir}/group_01/materials.json")
```

## API Reference

### USIFStructure

The main structure class with convenient methods:

#### Class Methods

- `from_source(source, **kwargs)` - **High-level interface (Recommended)**
  - Create from file path, pymatgen object, or ASE Atoms object
  - Automatically detects input type
  - Supports all file formats readable by pymatgen (CIF, POSCAR, XYZ, etc.)
  - Automatically performs symmetry analysis
  - Extracts Wyckoff sites for crystals
  - Supports forces, stress, energy, charges, magmoms
  - Additional properties via `**kwargs` are stored in `structure_properties.custom`
  - Example: `USIFStructure.from_source("structure.cif", energy=-10.5, calculator="VASP")`
  - Note: Named `from_source()` because `from` is a reserved keyword in Python

- `from_pymatgen(pmg_obj, **kwargs)` - Create from pymatgen Structure/Molecule
  - Automatically performs symmetry analysis
  - Extracts Wyckoff sites for crystals
  - Supports forces, stress, energy, charges, magmoms
  - Additional properties via `**kwargs` are stored in `structure_properties.custom`
  - Example: `calculator="VASP"` → `structure_properties.custom["calculator"] = "VASP"`
  - Note: For more flexibility, use `from_source()` instead

- `load(filename)` - Load structure from file
  - Auto-detects format (.usif uses encoder, others use JSON)

#### Instance Methods

- `to(filename=None, fmt=None, **kwargs)` - **Convert to various formats (Recommended)**
  - Similar to pymatgen's `to()` method
  - Supports: "usif", "pymatgen", "ase", and file formats (cif, poscar, xyz, etc.)
  - Auto-detects format from filename extension if `fmt` is not provided
  - Returns object for "pymatgen" and "ase", saves to file for other formats
  - Defaults to "pymatgen" if both filename and fmt are None
  - Example: `usif_struct.to("output.usif")`  # Auto-detects USIF format
  - Example: `usif_struct.to("output.cif")`  # Auto-detects CIF format
  - Example: `pmg_struct = usif_struct.to(fmt="pymatgen")`  # Returns object
  - Example: `usif_struct.to("output.cif", "cif")`  # Explicit format
  - Example: `pmg_struct2 = usif_struct.to()`  # Defaults to pymatgen if no args

- `save(filename, compression=CompressionType.GZIP)` - Save structure to file
  - `.usif` extension uses USIF encoder
  - Other extensions use JSON format

- `num_atoms()` - Get total number of atoms
- `is_crystal()` - Check if crystal structure
- `is_molecular()` - Check if molecular structure
- `is_symmetric()` - Check if using symmetric storage

### StructureConverter

Convert between USIF and various structure formats (pymatgen, ASE):

```python
from usif import StructureConverter
from pymatgen.core import Structure, Lattice
from ase import Atoms
import numpy as np

# From pymatgen to USIF
# Create a pymatgen structure
lattice = Lattice.cubic(5.64)
species = ["Na", "Cl"]
coords = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]
pmg_structure = Structure(lattice, species, coords)

# Define properties
forces_array = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])  # Nx3 array for N atoms
stress_tensor = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])  # 3x3 tensor

usif_struct = StructureConverter.from_pymatgen(
    pmg_structure,
    energy=-10.5,
    forces=forces_array,
    stress=stress_tensor
)

# From ASE to USIF
ase_atoms = Atoms('H2O', positions=[[0, 0, 0], [0.95, 0, 0], [0.95, 0.95, 0]])
forces_h2o = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])  # 3 atoms for H2O
usif_struct2 = StructureConverter.from_ase(
    ase_atoms,
    energy=-10.5,
    forces=forces_h2o
)

# From USIF to pymatgen
pmg_structure = StructureConverter.to_pymatgen(usif_struct)

# From USIF to ASE
ase_atoms = StructureConverter.to_ase(usif_struct)
```

**Note:** For most use cases, the high-level `USIFStructure.from_source()` interface is recommended as it automatically handles file reading and format detection.

### StructureContainer

HDF5-like container for multiple structures.

**File Extension**: Both `USIFStructure` and `StructureContainer` can use the `.usif` or `.usifc` file extension. The format is automatically detected by magic bytes:
- Structure files: magic bytes `b'USIF\x00\x00\x00'`
- Container files: magic bytes `b'USIFC\x00\x00'`

If you try to open a container file with `USIFStructure.load()` or vice versa, you'll get a helpful error message directing you to use the correct class.

#### Key Methods

- `add(structure, name=None, group="/", attributes=None)` - Add structure (returns hash)
- `add_structure(structure, name=None, group="/", attributes=None)` - Alias for `add()`
- `get(identifier)` - Get structure by hash or name
- `query(formula, properties, energy_range, group)` - Query structures
- `get_group(path)` - Get group by path
- `set_structure_attributes(identifier, attributes)` - Set structure metadata
- `get_structure_attributes(identifier)` - Get structure metadata
- `set_group_attribute(path, name, value)` - Set group metadata
- `get_group_attribute(path, name)` - Get group attribute
- `stats()` - Get container statistics

### USIF Encoder/Decoder

Low-level encoding/decoding:

```python
from usif import USIF, CompressionType

encoder = USIF(compression=CompressionType.GZIP)
data = encoder.encode(structure)
structure, hash = encoder.decode(data)
encoder.save(structure, "file.usif")
structure = encoder.load("file.usif")
```

### Utilities

#### MP Data Downloader

```python
from usif.utils import (
    download_mp_data,
    load_mp_group,
    convert_mp_to_usif,
    create_mp_data_archive,
    load_mp_data_from_archive
)

# Download MP data
stats = download_mp_data(api_key="YOUR_KEY", total_entries=100)

# Load and convert
docs = load_mp_group("path/to/group_01/materials.json")
usif_struct = convert_mp_to_usif(docs[0])

# Create/load archives
create_mp_data_archive("data/mp_structures")
load_mp_data_from_archive("data/mp_structures.zip")
```

#### Structure Optimizer

```python
from usif.utils import USIFOptimizer

optimizer = USIFOptimizer()
optimized = optimizer.optimize_structure(structure)
```

#### Benchmarking

```python
from usif.utils import USIFBenchmark

benchmark = USIFBenchmark()
results = benchmark.benchmark_compression(structure)
```

## Structure Types and Storage Modes

USIF supports different structure types and storage modes:

```
┌─────────────┬──────────────┬─────────────────┐
│             │ SYMMETRIC    │ FULL_ATOMIC     │
├─────────────┼──────────────┼─────────────────┤
│ CRYSTAL     │ Wyckoff      │ All atoms       │
│ (Periodic)  │ + lattice    │ + lattice       │
├─────────────┼──────────────┼─────────────────┤
│ MOLECULE    │ Point group  │ All atoms       │
│ (Molecular) │ (no lattice) │ (no lattice)    │
└─────────────┴──────────────┴─────────────────┘
```

- **SYMMETRIC**: Stores only unique sites with multiplicities (more compact)
- **FULL_ATOMIC**: Stores all atoms explicitly (supports per-atom properties)

## Properties

### Structure Properties

Built-in properties (direct attributes):
- `energy`: Total energy (float, eV)
- `stress`: Stress tensor in Voigt notation (6-element tuple, GPa)
- `volume`: Cell volume (float, Å³)
- `pressure`: Pressure (float, GPa)
- `temperature`: Temperature (float, K)

Custom properties (stored in `custom` dictionary):
- Any additional properties passed as `**kwargs` to `from_source()` or `from_pymatgen()`
- Access via `structure.structure_properties.custom["key"]`

```python
from usif import StructureProperties

# Create structure properties
props = StructureProperties(
    energy=-10.5,                                    # Built-in property
    volume=179.4,                                    # Built-in property
    stress=(1.0, 1.0, 1.0, 0.0, 0.0, 0.0),         # Built-in property (Voigt notation)
    custom={"calculator": "VASP", "kpoints": "4x4x4"}  # Custom properties
)

# When using from_source() or from_pymatgen(), custom properties can be passed as kwargs:
usif_struct = USIFStructure.from_source(
    "structure.cif",
    energy=-10.5,           # Built-in property
    calculator="VASP",       # Custom property → structure_properties.custom["calculator"]
    kpoints="4x4x4"          # Custom property → structure_properties.custom["kpoints"]
)
```

### Atomic Properties

```python
from usif import AtomicProperties

atom_props = AtomicProperties(
    force=(0.1, 0.2, 0.3),
    charge=0.5,
    magmom=2.0,
    velocity=(0.0, 0.0, 0.0),
    custom={"tag": "surface"}
)
```

## Examples

See the `examples/` directory for more examples:

- `example-1.py` - Basic structure creation and encoding
- `example-2.py` - Container usage with groups
- `download_mp_data.py` - Download Materials Project data for testing

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=usif --cov-report=term-missing

# Run specific test file
pytest tests/test_structure.py -v

# Test with Materials Project data (requires MP data in tests/data/)
pytest tests/test_mp_data.py -v
```

**Test Data:**
- MP test data is stored in `tests/data/mp_structures.zip`
- The zip file is tracked in git for reproducible testing
- To download fresh data: `python examples/download_mp_data.py`

## Performance

USIF provides significant compression benefits:

- **4-6x smaller** than traditional formats (CIF, POSCAR)
- **Automatic symmetry detection** reduces storage for symmetric structures
- **Efficient binary format** with optional compression
- **Fast random access** in containers with indexing

## Documentation

Additional documentation is available in the `docs/` directory:

- `ARCHITECTURE.md` - High-level architecture overview
- `BINARY_FORMAT.md` - Detailed binary format specification
- `DEVELOPMENT_PLAN.md` - Development roadmap and suggestions
- `IMPORT_STRUCTURE.md` - Import structure and dependency analysis

## License

This project is licensed under the USIF Non-Commercial License — academic use only.  
For commercial licensing, please contact: haidi@hfut.edu.cn

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/usif/issues)
- **Email**: haidi@hfut.edu.cn

---

**USIF v4.0** - Universal Structure Interchange Format - Making computational materials data efficient and interoperable.
