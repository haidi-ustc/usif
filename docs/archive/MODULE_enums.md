# Module: enums.py

## Overview

The `enums.py` module defines enumeration types used throughout the USIF system for type-safe classification of structures, storage modes, and compression algorithms. All enumerations inherit from Python's `IntEnum`, allowing them to be used both as integers (for binary serialization) and as named constants (for code readability).

**Purpose**: Provide type-safe enumeration constants that can be serialized as integers while maintaining readable code.

**Role in Architecture**: Foundation layer - defines core type system used by structure representation, encoding, and conversion modules.

## Architecture

The module contains three enumeration classes, all inheriting from `IntEnum`:

1. **StructureType**: Classifies structure as crystal or molecule
2. **StorageMode**: Specifies storage representation (symmetric or full atomic)
3. **CompressionType**: Indicates compression algorithm used

All enums use integer values starting from 0, making them suitable for binary serialization as uint8 values.

## Key Components

### StructureType Enumeration

Classifies whether a structure is periodic (crystal) or non-periodic (molecule).

**Values**:
- `CRYSTAL = 0`: Periodic structure with lattice parameters
- `MOLECULE = 1`: Non-periodic molecular structure without lattice

**Usage**:
```python
from usif import StructureType, USIFStructure

# Check structure type
if structure.structure_type == StructureType.CRYSTAL:
    print("Has lattice:", structure.lattice_matrix is not None)
elif structure.structure_type == StructureType.MOLECULE:
    print("No lattice for molecules")

# Use in structure creation
structure = USIFStructure(
    structure_type=StructureType.CRYSTAL,
    ...
)
```

**Binary Representation**: Serialized as 1 byte (uint8) in binary format.

**Design Rationale**: 
- Crystals require lattice matrix, molecules do not
- Different symmetry analysis methods (space group vs point group)
- Different storage optimizations possible

### StorageMode Enumeration

Specifies how atomic positions are stored in the structure.

**Values**:
- `SYMMETRIC = 0`: Store only unique sites with multiplicities (Wyckoff sites for crystals, point group sites for molecules)
- `FULL_ATOMIC = 1`: Store all atoms explicitly with coordinates

**Usage**:
```python
from usif import StorageMode, USIFStructure

# Check storage mode
if structure.storage_mode == StorageMode.SYMMETRIC:
    print("Using compact symmetric representation")
    print("Wyckoff sites:", structure.wyckoff_sites)
else:
    print("Using full atomic representation")
    print("Atom sites:", structure.atom_sites)

# Use in structure creation
structure = USIFStructure(
    storage_mode=StorageMode.SYMMETRIC,
    ...
)
```

**Binary Representation**: Serialized as 1 byte (uint8) in binary format.

**Design Rationale**:
- SYMMETRIC mode provides compression for high-symmetry structures
- FULL_ATOMIC mode required when per-atom properties are present
- Automatic selection based on symmetry and properties

### CompressionType Enumeration

Indicates the compression algorithm used for binary data.

**Values**:
- `NONE = 0`: No compression (raw binary data)
- `GZIP = 1`: GZIP compression (default, widely supported)

**Usage**:
```python
from usif import CompressionType, USIF

# Create encoder with specific compression
encoder = USIF(compression=CompressionType.GZIP)

# Save with compression
structure.save('file.usif', compression=CompressionType.GZIP)

# Load (compression detected from file)
loaded = USIFStructure.load('file.usif')
```

**Binary Representation**: Serialized as 1 byte (uint8) in binary format header.

**Design Rationale**:
- NONE for debugging or when compression overhead is not desired
- GZIP provides good compression with fast decompression
- Future: LZMA, BZIP2 can be added as 2, 3, etc.

## Dependencies

**Internal Dependencies**: None - foundational module.

**External Dependencies**: 
- `enum.IntEnum` from Python standard library

**Used By**:
- `structures/structure.py`: Uses StructureType and StorageMode
- `encoder.py`: Uses CompressionType
- `converter.py`: Uses StructureType and StorageMode
- `container.py`: Uses StructureType and StorageMode for indexing

## Data Structures

No complex data structures - only enumeration classes with integer values.

## Usage Patterns

### Type Checking Pattern

```python
from usif import StructureType, StorageMode

# Type checking
if structure.structure_type == StructureType.CRYSTAL:
    # Crystal-specific operations
    lattice = structure.lattice_matrix
    spacegroup = structure.spacegroup
else:
    # Molecule-specific operations
    point_group = structure.point_group
```

### Storage Mode Selection Pattern

```python
from usif import StorageMode

# Conditional logic based on storage mode
if structure.storage_mode == StorageMode.SYMMETRIC:
    # Access symmetric representation
    sites = structure.wyckoff_sites or structure.point_group_sites
    total_atoms = sum(site.multiplicity for site in sites)
else:
    # Access full atomic representation
    sites = structure.atom_sites
    total_atoms = len(sites)
```

### Compression Selection Pattern

```python
from usif import CompressionType, USIF

# Select compression based on use case
if fast_access_needed:
    compression = CompressionType.NONE
else:
    compression = CompressionType.GZIP

encoder = USIF(compression=compression)
```

## Implementation Details

### IntEnum Choice

Using `IntEnum` instead of `Enum` provides:
- Integer comparison: `StructureType.CRYSTAL == 0` is True
- Binary serialization: Can directly use as integer values
- Backward compatibility: Can compare with integer literals
- Type safety: Still provides named constants

### Integer Values

All enums start from 0 and increment by 1:
- Efficient binary encoding (uint8 for all)
- Simple validation (check if value < max)
- Easy to extend (add new values sequentially)

### Type Safety

While IntEnum allows integer comparison, best practice is:
```python
# Good: Use enum constant
if structure.structure_type == StructureType.CRYSTAL:
    ...

# Avoid: Use integer literal
if structure.structure_type == 0:  # Less readable
    ...
```

## Testing Considerations

**Test Coverage Areas**:
- Enum value correctness (verify integer values)
- Enum comparison (test ==, !=, <, > operations)
- Binary serialization (verify enum -> int -> enum round-trip)
- Invalid value handling (test with out-of-range integers)

**Important Test Cases**:
- Enum to integer conversion
- Integer to enum conversion (with validation)
- Enum comparison operations
- Enum iteration (if needed)

## Future Enhancements

1. **Additional Compression Types**: Add LZMA (2), BZIP2 (3) when implemented
2. **Enum Validation**: Add validation methods to check valid enum values
3. **String Conversion**: Add `from_string()` methods for configuration files
4. **Extended Storage Modes**: Consider additional modes if needed (e.g., compressed atomic)
5. **Enum Metadata**: Add descriptions or documentation strings to enum values

## Related Modules

- **constants.py**: Related constants (BinaryFormat, SymmetryConstants)
- **structures/structure.py**: Primary consumer of StructureType and StorageMode
- **encoder.py**: Uses CompressionType for compression selection
- **converter.py**: Uses StructureType and StorageMode for conversion logic

