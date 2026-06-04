# USIF Modular Package Structure

## Overview

The USIF package has been refactored into a clean, modular structure for better maintainability and organization.

## Package Structure

```
usif/
├── __init__.py          # Main entry point with backward compatibility
├── constants.py         # Binary format constants
├── exceptions.py        # Exception classes
├── enums.py            # Enumeration types
├── encoder.py          # Encoder/decoder
├── converter.py        # Pymatgen converter
├── container.py        # Structure container
├── properties/         # Property system
│   ├── __init__.py
│   ├── definitions.py  # Property definitions
│   ├── serializer.py   # Property serialization
│   ├── registry.py     # Property registry
│   ├── atomic.py       # Atomic properties
│   └── structure.py    # Structure properties
├── structures/         # Structure system
│   ├── __init__.py
│   ├── sites.py        # Site representations
│   └── structure.py    # Main structure class
└── utils/              # Utility modules
    ├── __init__.py
    ├── optimizer.py    # Structure optimizer
    └── benchmark.py    # Benchmarking utilities
```

## Usage

The package maintains full backward compatibility. All imports work as before:

```python
from usif import USIF, USIFStructure, StructureType, StorageMode
from usif import PropertyRegistry, AtomicProperties, StructureProperties
from usif import StructureConverter, StructureContainer
```

## Module Imports

You can also import from specific modules:

```python
from usif.properties import PropertyDefinition, PropertySerializer
from usif.structures import WyckoffSite, AtomSite
from usif.utils import USIFOptimizer, USIFBenchmark
```

## Testing

Run all tests:

```bash
python3 run_tests.py
```

Or use pytest:

```bash
pytest test_all.py -v
```

## Benefits

1. **Modularity**: Clear separation of concerns
2. **Maintainability**: Easier to locate and modify code
3. **Extensibility**: Simple to add new features
4. **Backward Compatibility**: All existing code continues to work
5. **Clean Structure**: Follows Python package best practices

