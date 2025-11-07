# Module: structures/structure.py

## Overview

The `structure.py` module provides the `USIFStructure` class, the core structure representation for the USIF format. This is the central class that unifies crystal and molecule representation, supporting both symmetric (compact) and full atomic (explicit) storage modes. The class implements MSONable interface for JSON serialization and provides comprehensive file I/O capabilities.

**Purpose**: Provide a unified, type-safe structure representation that handles both periodic (crystals) and non-periodic (molecules) structures with automatic validation, property management, and format conversion.

**Role in Architecture**: Core component - the primary data structure used throughout the USIF system for structure representation, storage, and manipulation.

## Architecture

The `USIFStructure` class is a large, feature-rich class (~885 lines) that implements:

1. **Structure Representation**: Unified representation for crystals and molecules
2. **Storage Modes**: Support for SYMMETRIC and FULL_ATOMIC modes
3. **Property Management**: Integration with StructureProperties and AtomicProperties
4. **File I/O**: Save/load with automatic format detection
5. **Format Conversion**: Conversion to/from pymatgen and ASE formats
6. **Validation**: Comprehensive structure configuration validation
7. **MSONable Interface**: JSON serialization support

The class uses `__slots__` for memory efficiency and implements the MSONable interface for compatibility with materials science workflows.

## Key Components

### USIFStructure Class

The main class representing atomic structures in USIF format.

#### Class Attributes (via __slots__)

- `structure_type: StructureType`: CRYSTAL or MOLECULE
- `storage_mode: StorageMode`: SYMMETRIC or FULL_ATOMIC
- `lattice_matrix: Optional[np.ndarray]`: 3×3 lattice matrix (crystals only)
- `spacegroup: int`: Space group number (crystals, default: 1)
- `point_group: Optional[str]`: Point group symbol (molecules, e.g., "C2v")
- `wyckoff_sites: Optional[List[WyckoffSite]]`: Wyckoff sites (CRYSTAL + SYMMETRIC)
- `point_group_sites: Optional[List[PointGroupSite]]`: Point group sites (MOLECULE + SYMMETRIC)
- `atom_sites: Optional[List[AtomSite]]`: Atom sites (FULL_ATOMIC mode)
- `structure_properties: StructureProperties`: Structure-level properties
- `formula: str`: Chemical formula string

#### Key Methods

**Initialization and Validation**:

- `__init__()`: Initialize USIFStructure with validation
- `_validate_structure()`: Validate structure configuration consistency

**Type Checking**:

- `is_crystal() -> bool`: Check if structure is periodic (crystal)
- `is_molecular() -> bool`: Check if structure is non-periodic (molecule)
- `is_symmetric() -> bool`: Check if using SYMMETRIC storage mode

**Structure Information**:

- `num_atoms() -> int`: Get total number of atoms (from multiplicities or site count)

**Serialization**:

- `as_dict() -> dict`: Convert to MSONable dictionary for JSON serialization
- `from_dict(d: dict) -> USIFStructure`: Create from MSONable dictionary

**File I/O**:

- `save(filename, compression=CompressionType.GZIP) -> None`: Save structure to file
- `load(filename) -> USIFStructure`: Load structure from file (class method)

**Format Conversion**:

- `from_source(source, **kwargs) -> USIFStructure`: High-level interface to create from various sources (class method)
- `from_pymatgen(pmg_obj, **kwargs) -> USIFStructure`: Create from pymatgen object (class method)
- `to(filename=None, fmt=None, **kwargs) -> Optional[Any]`: Convert to other formats or save to file

**String Representation**:

- `__str__() -> str`: Human-readable string representation
- `__repr__() -> str`: Developer-friendly representation

**Special Attribute Access**:

- `__getattr__()`: Allows `structure.from` as alias for `structure.from_source` (since `from` is reserved keyword)

## Dependencies

**Internal Dependencies**:
- `usif.enums`: StructureType, StorageMode, CompressionType
- `usif.exceptions`: ValidationError, StorageError
- `usif.structures.sites`: WyckoffSite, PointGroupSite, AtomSite
- `usif.properties.structure`: StructureProperties
- `usif.properties.atomic`: AtomicProperties
- `usif.converter`: StructureConverter (for format conversion)
- `usif.encoder`: USIF (for binary encoding/decoding)

**External Dependencies**:
- `numpy`: For lattice matrix and array operations
- `monty.json`: MSONable interface for JSON serialization
- `pymatgen`: Optional, for file reading and format conversion
- `ase`: Optional, for ASE Atoms conversion

**Used By**: All modules that work with structures:
- `encoder.py`: Encodes/decodes USIFStructure
- `converter.py`: Converts to/from USIFStructure
- `container.py`: Stores USIFStructure instances
- `utils/optimizer.py`: Optimizes USIFStructure
- `utils/benchmark.py`: Benchmarks USIFStructure

## Data Structures

### Structure Type Matrix

The class implements a 2×2 matrix of structure types and storage modes:

| | SYMMETRIC | FULL_ATOMIC |
|---|---|---|
| **CRYSTAL** | WyckoffSite + lattice | AtomSite + lattice |
| **MOLECULE** | PointGroupSite (no lattice) | AtomSite (no lattice) |

### Attribute Organization

Attributes are organized by structure type and storage mode:
- **Crystal-specific**: `lattice_matrix`, `spacegroup`, `wyckoff_sites`
- **Molecule-specific**: `point_group`, `point_group_sites`
- **Full atomic**: `atom_sites` (used by both types)
- **Common**: `structure_properties`, `formula`

## Usage Patterns

### Creating Structures Directly

```python
from usif import USIFStructure, StructureType, StorageMode
from usif.structures.sites import WyckoffSite
import numpy as np

# Create crystal structure with Wyckoff sites
lattice = np.array([[5.64, 0.0, 0.0], [0.0, 5.64, 0.0], [0.0, 0.0, 5.64]])
wyckoff_sites = [
    WyckoffSite(atomic_number=11, multiplicity=4, coords=(0.0, 0.0, 0.0)),
    WyckoffSite(atomic_number=17, multiplicity=4, coords=(0.5, 0.5, 0.5))
]

structure = USIFStructure(
    structure_type=StructureType.CRYSTAL,
    storage_mode=StorageMode.SYMMETRIC,
    lattice_matrix=lattice,
    spacegroup=225,
    wyckoff_sites=wyckoff_sites,
    formula="NaCl"
)
```

### Creating from Files (Recommended)

```python
from usif import USIFStructure

# From file with properties
structure = USIFStructure.from_source(
    "structure.cif",
    energy=-10.5,      # Built-in property
    volume=179.4,      # Built-in property
    calculator="VASP"  # Custom property
)
```

### Creating from Pymatgen Objects

```python
from usif import USIFStructure
from pymatgen.core import Structure, Lattice

# Create pymatgen structure
lattice = Lattice.cubic(5.64)
pmg_struct = Structure(lattice, ["Na", "Cl"], [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])

# Convert to USIF
usif_struct = USIFStructure.from_source(
    pmg_struct,
    energy=-20.8,
    volume=179.4
)
```

### Saving and Loading

```python
from usif import USIFStructure, CompressionType

# Save to USIF format
structure.save("structure.usif", compression=CompressionType.GZIP)

# Save to JSON format
structure.save("structure.json")

# Load from USIF format
loaded = USIFStructure.load("structure.usif")

# Load from JSON format
loaded = USIFStructure.load("structure.json")
```

### Format Conversion

```python
from usif import USIFStructure

# Convert to pymatgen
pmg_struct = structure.to(fmt="pymatgen")

# Convert to ASE
ase_atoms = structure.to(fmt="ase")

# Save to CIF
structure.to("output.cif")  # Auto-detects format from extension

# Save to POSCAR
structure.to("output.poscar", fmt="poscar")
```

### Structure Inspection

```python
# Check structure type
if structure.is_crystal():
    print(f"Space group: {structure.spacegroup}")
    print(f"Lattice:\n{structure.lattice_matrix}")

if structure.is_molecular():
    print(f"Point group: {structure.point_group}")

# Check storage mode
if structure.is_symmetric():
    print("Using compact symmetric storage")
    if structure.is_crystal():
        print(f"Wyckoff sites: {len(structure.wyckoff_sites)}")
    else:
        print(f"Point group sites: {len(structure.point_group_sites)}")
else:
    print("Using full atomic storage")
    print(f"Atom sites: {len(structure.atom_sites)}")

# Get structure information
print(f"Formula: {structure.formula}")
print(f"Number of atoms: {structure.num_atoms()}")
print(f"Energy: {structure.structure_properties.energy} eV")
```

## Implementation Details

### Validation Logic

The `_validate_structure()` method enforces:

1. **Crystal structures**:
   - Must have `lattice_matrix` (not None)
   - SYMMETRIC mode requires non-empty `wyckoff_sites`
   - FULL_ATOMIC mode requires non-empty `atom_sites`

2. **Molecular structures**:
   - Must NOT have `lattice_matrix` (must be None)
   - SYMMETRIC mode requires non-empty `point_group_sites`
   - FULL_ATOMIC mode requires non-empty `atom_sites`

This ensures structure configuration consistency and prevents invalid states.

### from_source() Method

The `from_source()` method provides a high-level interface that:
1. Detects input type (file path, pymatgen object, ASE object)
2. Delegates to appropriate converter method
3. Handles property attachment
4. Performs automatic symmetry analysis

This is the recommended way to create USIF structures from external sources.

### to() Method

The `to()` method provides flexible format conversion:
- Auto-detects format from file extension if `fmt` not provided
- Returns objects for "pymatgen" and "ase" formats
- Saves to file for other formats (CIF, POSCAR, XYZ, etc.)
- Supports USIF format saving with compression options

### File Format Detection

The `save()` and `load()` methods automatically detect format:
- `.usif` extension: Uses USIF binary encoder/decoder
- Other extensions: Uses JSON (MSONable) format
- Container files (`.usifc`): Detected and raises appropriate error

### MSONable Interface

Implements MSONable for JSON serialization:
- `as_dict()`: Converts to dictionary with `@module` and `@class` metadata
- `from_dict()`: Reconstructs from dictionary
- Compatible with monty.json serialization
- Enables integration with materials science workflows

### Memory Efficiency

Uses `__slots__` to:
- Reduce memory footprint
- Prevent accidental attribute creation
- Improve attribute access speed

## Testing Considerations

**Test Coverage Areas**:
- Structure creation with all mode combinations
- Validation logic (invalid configurations)
- File I/O (save/load round-trips)
- Format conversion (to/from pymatgen, ASE)
- Property attachment and retrieval
- Structure type checking methods
- Atom counting (symmetric vs full atomic)
- MSONable serialization/deserialization

**Important Test Cases**:
- Valid structure configurations (all 4 combinations)
- Invalid configurations (should raise ValidationError)
- File format detection and handling
- Format conversion accuracy
- Property preservation through save/load
- Edge cases (empty structures, single atom, etc.)

## Future Enhancements

1. **Structure Manipulation**: Methods for structure modification (add/remove atoms, transform)
2. **Structure Comparison**: Methods for structure similarity/difference
3. **Structure Analysis**: Built-in analysis methods (density, volume, etc.)
4. **Lazy Loading**: Lazy evaluation for large structures
5. **Structure Caching**: Cache computed properties (formula, num_atoms, etc.)
6. **Validation Enhancements**: More detailed validation with error messages
7. **Structure Merging**: Methods to combine structures
8. **Structure Filtering**: Methods to filter atoms/sites based on criteria

## Related Modules

- **structures/sites.py**: Provides WyckoffSite, PointGroupSite, AtomSite
- **converter.py**: Handles format conversion logic
- **encoder.py**: Handles binary encoding/decoding
- **properties/structure.py**: StructureProperties class
- **properties/atomic.py**: AtomicProperties class
- **enums.py**: StructureType, StorageMode, CompressionType

