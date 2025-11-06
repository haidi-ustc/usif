# USIF (Universal Structure Interchange Format) v4.0

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Unified format for crystals and molecules with intelligent compression**

USIF is a next-generation file format designed for storing and exchanging atomic structure data with unprecedented efficiency and flexibility. It provides a unified interface for both periodic (crystals) and non-periodic (molecules) structures with intelligent compression capabilities.

## Quick Start

### Installation

```bash
# Basic installation
pip install -e .

# With pymatgen support
pip install -e ".[pymatgen]"

# Development installation with all dependencies
pip install -e ".[all]"
```

### Basic Usage

```python
from usif import USIF, USIFStructure, StructureType, StorageMode
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
    calculator="VASP"
)

structure = USIFStructure(
    structure_type=StructureType.PERIODIC,
    storage_mode=StorageMode.SYMMETRIC,
    lattice_matrix=lattice_matrix,
    spacegroup=225,
    wyckoff_sites=wyckoff_sites,
    structure_properties=structure_props,
    formula="NaCl"
)

# Encode to USIF format
encoder = USIF()
usif_data = encoder.encode(structure)

print(f"Encoded size: {len(usif_data)} bytes")
print(f"Structure hash: {encoder.get_structure_hash(structure)}")

# Decode back
decoded_structure, hash_value = encoder.decode(usif_data)
print(f"Decoded formula: {decoded_structure.formula}")
```

## Key Features

- **Unified Structure Support**: Crystals and molecules with seamless conversion
- **Intelligent Compression**: 4-6x compression vs traditional formats
- **Modular Property System**: Type-safe properties with units and validation
- **Advanced Container Features**: HDF5-like organization with hierarchical groups

## Documentation

For detailed documentation, see:
- [Full Documentation](docs/README.md)
- [Modular Structure Guide](docs/README_MODULAR.md)

## Testing

Run the test suite:

```bash
python3 run_tests.py
```

Or with pytest:

```bash
pytest tests/ -v
```

## License

This project is licensed under the USIF Non-Commercial License — academic use only.  
For commercial licensing, please contact: haidi@hfut.edu.cn

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/usif/issues)
- **Email**: haidi@hfut.edu.cn

---

**USIF v4.0** - Universal Structure Interchange Format - Making computational materials data efficient and interoperable.

