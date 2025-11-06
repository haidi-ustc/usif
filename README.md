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

## Installation

```bash
# Basic installation
pip install -e .

# With pymatgen support (recommended)
pip install -e ".[pymatgen]"

# Development installation with all dependencies
pip install -e ".[all]"
```

## Quick Start

### Creating Structures from Pymatgen (Recommended)

The easiest way to create USIF structures is from pymatgen objects with automatic symmetry analysis:

```python
from pymatgen.core import Structure
from usif import USIFStructure

# Load from CIF file
pmg_struct = Structure.from_file("structure.cif")

# Convert to USIF with automatic Wyckoff site extraction
# Custom properties can be passed as keyword arguments
usif_struct = USIFStructure.from_pymatgen(
    pmg_struct,
    energy=-10.5,
    calculator="VASP"  # Stored in structure_properties.custom
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

### File I/O

USIF structures support convenient save/load methods:

```python
# Save to .usif format (uses encoder)
structure.save("structure.usif")

# Save to JSON format (human-readable)
structure.save("structure.json")

# Load from file (auto-detects format)
loaded = USIFStructure.load("structure.usif")
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
with StructureContainer("structures.usif", mode='w') as container:
    # Add structures with names and groups
    container.add_structure(
        structure1, 
        name="NaCl_001",
        group="/materials/crystals",
        attributes={"author": "John Doe", "date": "2024-01-01"}
    )
    
    container.add_structure(
        structure2,
        name="H2O_001",
        group="/materials/molecules"
    )
    
    # Set group attributes
    container.set_group_attribute("/materials", "description", "Material database")
    
    # Query structures
    results = container.query(formula="NaCl", group="/materials/crystals")
    
    # Walk through groups
    for path, group in container.walk_groups():
        print(f"Group: {path}, Structures: {len(group.list_structures())}")

# Read from container
with StructureContainer("structures.usif", mode='r') as container:
    structure = container.get("NaCl_001")
    attrs = container.get_structure_attributes("NaCl_001")
```

## API Reference

### USIFStructure

The main structure class with convenient methods:

#### Class Methods

- `from_pymatgen(pmg_obj, **kwargs)` - Create from pymatgen Structure/Molecule
  - Automatically performs symmetry analysis
  - Extracts Wyckoff sites for crystals
  - Supports forces, stress, energy, charges, magmoms
  - Additional properties via `**kwargs` are stored in `structure_properties.custom`
  - Example: `calculator="VASP"` → `structure_properties.custom["calculator"] = "VASP"`

- `load(filename)` - Load structure from file
  - Auto-detects format (.usif uses encoder, others use JSON)

#### Instance Methods

- `save(filename, compression=CompressionType.GZIP)` - Save structure to file
  - `.usif` extension uses USIF encoder
  - Other extensions use JSON format

- `num_atoms()` - Get total number of atoms
- `is_crystal()` - Check if crystal structure
- `is_molecular()` - Check if molecular structure
- `is_symmetric()` - Check if using symmetric storage

### StructureConverter

Convert between USIF and pymatgen formats:

```python
from usif import StructureConverter

# From pymatgen to USIF
usif_struct = StructureConverter.from_pymatgen(
    pmg_structure,
    energy=-10.5,
    forces=forces_array,
    stress=stress_tensor
)

# From USIF to pymatgen
pmg_structure = StructureConverter.to_pymatgen(usif_struct)
```

### StructureContainer

HDF5-like container for multiple structures.

**File Extension**: Both `USIFStructure` and `StructureContainer` can use the `.usif` file extension. The format is automatically detected by magic bytes:
- Structure files: magic bytes `b'USIF\x00\x00\x00'`
- Container files: magic bytes `b'USIFC\x00\x00'`

If you try to open a container file with `USIFStructure.load()` or vice versa, you'll get a helpful error message directing you to use the correct class.

#### Key Methods

- `add_structure(structure, name, group="/", attributes=None)` - Add structure
- `get(identifier)` - Get structure by hash or name
- `query(formula, properties, energy_range, group)` - Query structures
- `create_group(path)` - Create group hierarchy
- `walk_groups(path="/")` - Walk through group hierarchy
- `set_structure_attributes(name, attributes)` - Set structure metadata
- `set_group_attribute(path, name, value)` - Set group metadata

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

```python
from usif import StructureProperties

props = StructureProperties(
    energy=-10.5,
    volume=179.4,
    stress=(1.0, 1.0, 1.0, 0.0, 0.0, 0.0),  # Voigt notation
    custom={"calculator": "VASP", "kpoints": "4x4x4"}  # Custom properties
)

# Note: When using from_pymatgen(), you can pass custom properties as kwargs:
# USIFStructure.from_pymatgen(pmg_struct, calculator="VASP", kpoints="4x4x4")
# This is equivalent to custom={"calculator": "VASP", "kpoints": "4x4x4"}
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

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=usif --cov-report=term-missing

# Run specific test file
pytest tests/test_structure.py -v
```

## Performance

USIF provides significant compression benefits:

- **4-6x smaller** than traditional formats (CIF, POSCAR)
- **Automatic symmetry detection** reduces storage for symmetric structures
- **Efficient binary format** with optional compression
- **Fast random access** in containers with indexing

## License

This project is licensed under the USIF Non-Commercial License — academic use only.  
For commercial licensing, please contact: haidi@hfut.edu.cn

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/usif/issues)
- **Email**: haidi@hfut.edu.cn

---

**USIF v4.0** - Universal Structure Interchange Format - Making computational materials data efficient and interoperable.
