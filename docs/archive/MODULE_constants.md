# Module: constants.py

## Overview

The `constants.py` module provides fundamental constants used throughout the USIF format system. It defines two main classes: `BinaryFormat` for binary serialization format strings and `SymmetryConstants` for symmetry analysis parameters. This module has no dependencies on other USIF modules, making it a foundational component that can be imported safely by any other module.

**Purpose**: Centralize all format-related constants and symmetry analysis parameters to ensure consistency across the codebase.

**Role in Architecture**: Foundation layer - provides constants used by encoder, decoder, property serializer, and structure converter modules.

## Architecture

The module consists of two static classes (no instantiation required):

1. **BinaryFormat**: Class containing struct format strings for binary encoding/decoding
2. **SymmetryConstants**: Class containing floating-point constants for symmetry analysis

Both classes use class attributes (no instance methods except one static method), following a constants-only pattern.

## Key Components

### BinaryFormat Class

A static class providing format strings for Python's `struct` module. All format strings explicitly specify little-endian byte order (`<` prefix) to ensure cross-platform compatibility.

#### Integer Format Strings

- **Unsigned Integers**:
  - `UINT8 = '<B'`: 1-byte unsigned integer (0-255)
  - `UINT16 = '<H'`: 2-byte unsigned integer (0-65,535)
  - `UINT32 = '<I'`: 4-byte unsigned integer (0-4,294,967,295)
  - `UINT64 = '<Q'`: 8-byte unsigned integer (0-18,446,744,073,709,551,615)

- **Signed Integers**:
  - `INT8 = '<b'`: 1-byte signed integer (-128 to 127)
  - `INT16 = '<h'`: 2-byte signed integer (-32,768 to 32,767)
  - `INT32 = '<i'`: 4-byte signed integer (-2,147,483,648 to 2,147,483,647)
  - `INT64 = '<q'`: 8-byte signed integer (-9,223,372,036,854,775,808 to 9,223,372,036,854,775,807)

#### Floating Point Format Strings

- `FLOAT32 = '<f'`: 4-byte single-precision float (~7 decimal digits precision)
- `FLOAT64 = '<d'`: 8-byte double-precision float (~15 decimal digits precision)

#### Boolean Format String

- `BOOL = '<?'`: 1-byte boolean (0x00 = false, 0x01 = true)

#### Special Flags

- `LONG_COUNT_FLAG = 0xFF`: Indicates that a 4-byte count follows (for variable-length encoding)
- `NULL_FLAG = 0xFE`: Reserved for null value indication
- `NAN_FLAG = 0xFD`: Reserved for NaN value indication

#### Static Method

- `array(fmt: str, count: int) -> str`: Creates array format string for struct.pack/unpack
  - Strips endianness prefix from format string
  - Returns format string like `'9f'` for 9 float32 values
  - Used for serializing multi-dimensional arrays

**Usage Example**:
```python
import struct
from usif import BinaryFormat

# Pack a single float32
data = struct.pack(BinaryFormat.FLOAT32, 3.14159)

# Pack an array of 3 float32 values
coords = [1.0, 2.0, 3.0]
data = struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *coords)

# Pack a uint16
count = struct.pack(BinaryFormat.UINT16, 42)
```

### SymmetryConstants Class

A static class containing tolerance and precision constants for symmetry analysis and structure comparison operations.

#### Constants

- `DEFAULT_SYMMETRY_TOLERANCE: float = 1e-3`: Default tolerance for symmetry analysis in Angstroms (0.001 Å)
  - Used by pymatgen's SpacegroupAnalyzer and PointGroupAnalyzer
  - Determines how close atoms must be to be considered equivalent
  - Also used for property value comparisons

- `DEFAULT_SPACEGROUP_TOLERANCE: float = 0.1`: Tolerance for spacegroup analysis in Angstroms (0.1 Å)
  - Used for space group determination
  - Larger tolerance for initial symmetry detection

- `MOLECULAR_EQUIVALENCE_TOLERANCE: float = 0.01`: Tolerance for molecular symmetry equivalence distance in Angstroms (0.01 Å)
  - Used specifically for molecular structures
  - Tighter tolerance than crystal symmetry

- `COORDINATE_TOLERANCE: float = 1e-6`: Coordinate comparison tolerance in Angstroms (0.000001 Å)
  - Used for coordinate equality checks
  - Very tight tolerance for precise coordinate matching

**Usage Example**:
```python
from usif import SymmetryConstants
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

# Use default tolerance for symmetry analysis
sga = SpacegroupAnalyzer(structure, 
                        symprec=SymmetryConstants.DEFAULT_SPACEGROUP_TOLERANCE)

# Check coordinate equality with tolerance
def coordinates_equal(coord1, coord2):
    diff = abs(coord1 - coord2)
    return diff < SymmetryConstants.COORDINATE_TOLERANCE
```

## Dependencies

**Internal Dependencies**: None - this is a foundational module with no USIF dependencies.

**External Dependencies**: None - uses only Python standard library.

**Used By**:
- `encoder.py`: Uses BinaryFormat for binary serialization
- `properties/serializer.py`: Uses BinaryFormat for property serialization
- `converter.py`: Uses SymmetryConstants for symmetry analysis
- `structures/structure.py`: Uses SymmetryConstants for coordinate comparisons
- `properties/atomic.py`: Uses SymmetryConstants for property equality checks

## Data Structures

No complex data structures - only class attributes (strings, integers, floats).

## Usage Patterns

### Common Pattern: Binary Serialization

```python
import struct
from usif import BinaryFormat

# Standard pattern for encoding
def encode_value(value, format_str):
    return struct.pack(format_str, value)

# Standard pattern for decoding
def decode_value(data, format_str):
    return struct.unpack(format_str, data)[0]
```

### Common Pattern: Array Serialization

```python
from usif import BinaryFormat
import struct

# Encode array
values = [1.0, 2.0, 3.0]
fmt = BinaryFormat.array(BinaryFormat.FLOAT32, len(values))
data = struct.pack(fmt, *values)

# Decode array
decoded = struct.unpack(fmt, data)
```

### Common Pattern: Symmetry Analysis

```python
from usif import SymmetryConstants
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

# Use constants for consistent tolerance
sga = SpacegroupAnalyzer(
    structure,
    symprec=SymmetryConstants.DEFAULT_SPACEGROUP_TOLERANCE
)
```

## Implementation Details

### Endianness

All format strings explicitly use little-endian (`<` prefix) to ensure:
- Cross-platform compatibility
- Consistent binary format regardless of host architecture
- Predictable byte ordering for network transfer

### Array Format Generation

The `array()` method strips endianness prefix before creating array format because:
- Array format strings in struct don't support endianness prefix directly
- Endianness is applied at the struct.pack/unpack level
- Format like `'9f'` is more efficient than `'<9f'` (though both work)

### Tolerance Values

Tolerance constants are carefully chosen:
- `DEFAULT_SYMMETRY_TOLERANCE` (1e-3 Å): Balances accuracy with computational efficiency, also used for property value comparisons
- `DEFAULT_SPACEGROUP_TOLERANCE` (0.1 Å): Larger tolerance for space group determination
- `MOLECULAR_EQUIVALENCE_TOLERANCE` (0.01 Å): Used for molecular symmetry equivalence
- `COORDINATE_TOLERANCE` (1e-6 Å): Very tight for precise coordinate matching

## Testing Considerations

**Test Coverage Areas**:
- Format string correctness (verify struct.pack/unpack round-trips)
- Array format generation (test with various sizes and types)
- Tolerance constant values (verify they're appropriate for use cases)
- Endianness consistency (test on different architectures if possible)

**Important Test Cases**:
- Round-trip encoding/decoding with all format types
- Array format with edge cases (empty, single element, large arrays)
- Tolerance-based comparisons with known values

## Future Enhancements

1. **Additional Format Types**: Support for complex numbers, quaternions if needed
2. **Big-Endian Support**: Optional big-endian format strings for specific use cases
3. **Format Validation**: Runtime validation of format strings
4. **Tolerance Configuration**: Allow user-configurable tolerance values while maintaining defaults
5. **Unit Conversion**: Integration with units.py for tolerance values in different units

## Related Modules

- **encoder.py**: Primary consumer of BinaryFormat constants
- **properties/serializer.py**: Uses BinaryFormat for property serialization
- **converter.py**: Uses SymmetryConstants for symmetry analysis
- **enums.py**: Related enumeration types (StructureType, StorageMode, CompressionType)

