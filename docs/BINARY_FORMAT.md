# USIF Binary Format Specification

## Overview

This document specifies the exact binary format for USIF (Universal Structure Interchange Format) files. The format is designed for efficient storage of atomic structures with support for compression and integrity checking.

**Format Version**: 4  
**Endianness**: Little-endian (all multi-byte values)  
**Byte Order**: All integers and floats use little-endian byte order (`<` prefix in struct format)

## File Structure

A USIF file consists of two main parts:

1. **Header** (64 bytes, fixed size)
2. **Compressed Data** (variable size)

```
┌─────────────────────────────────────────┐
│           Header (64 bytes)              │
├─────────────────────────────────────────┤
│  Magic bytes: 7 bytes                   │
│  Version: 1 byte                        │
│  Raw data size: 4 bytes                 │
│  Compressed data size: 4 bytes          │
│  Compression type: 1 byte               │
│  Hash (SHA-256): 32 bytes               │
│  Reserved: 15 bytes                     │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│      Compressed Data (variable)         │
│  (GZIP compressed structure data)       │
└─────────────────────────────────────────┘
```

## Header Format

### Byte Layout

| Offset | Size | Field | Type | Description |
|--------|------|-------|------|-------------|
| 0-6 | 7 | Magic | bytes | `b'USIF\x00\x00\x00'` |
| 7 | 1 | Version | uint8 | Format version (currently 5) |
| 8-11 | 4 | Raw Size | uint32 | Uncompressed data size in bytes |
| 12-15 | 4 | Compressed Size | uint32 | Compressed data size in bytes |
| 16 | 1 | Compression | uint8 | Compression type (0=None, 1=GZIP) |
| 17-48 | 32 | Hash | bytes | SHA-256 hash of raw data |
| 49-63 | 15 | Reserved | bytes | Reserved for future use (all zeros) |

### Compression Types

| Value | Type | Description |
|-------|------|-------------|
| 0 | NONE | No compression |
| 1 | GZIP | GZIP compression (default) |
| 2 | LZMA | LZMA compression (planned) |
| 3 | BZIP2 | BZIP2 compression (planned) |

## Raw Data Format (Uncompressed)

The raw data section contains the serialized structure. After decompression, the data follows this format:

### Structure Data Layout

```
┌─────────────────────────────────────────┐
│  Structure Type: 1 byte (uint8)         │
│    0 = CRYSTAL, 1 = MOLECULE            │
├─────────────────────────────────────────┤
│  Storage Mode: 1 byte (uint8)           │
│    0 = SYMMETRIC, 1 = FULL_ATOMIC       │
├─────────────────────────────────────────┤
│  Structure-Specific Data (variable)     │
│  (see sections below)                   │
├─────────────────────────────────────────┤
│  Structure Properties (variable)        │
│  (see Property Format section)          │
├─────────────────────────────────────────┤
│  Formula Length: 2 bytes (uint16)       │
├─────────────────────────────────────────┤
│  Formula: N bytes (UTF-8 string)        │
└─────────────────────────────────────────┘
```

### Crystal Structure (Structure Type = 0)

#### SYMMETRIC Mode

```
┌─────────────────────────────────────────┐
│  Lattice Matrix: 36 bytes               │
│    3x3 matrix, float32, row-major       │
│    [a1x a1y a1z]                        │
│    [a2x a2y a2z]                        │
│    [a3x a3y a3z]                        │
├─────────────────────────────────────────┤
│  Space Group: 2 bytes (uint16)          │
├─────────────────────────────────────────┤
│  Number of Wyckoff Sites: 1 byte (uint8)│
├─────────────────────────────────────────┤
│  Wyckoff Sites (repeated N times):      │
│    ┌─────────────────────────────────┐  │
│    │ Atomic Number: 1 byte (uint8)   │  │
│    │ Multiplicity: 2 bytes (uint16)  │  │
│    │ Coordinates: 12 bytes           │  │
│    │   (x, y, z) as float32          │  │
│    │ Occupancy: 4 bytes (float32)    │  │
│    └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Wyckoff Site Size**: 1 + 2 + 12 + 4 = 19 bytes per site

#### FULL_ATOMIC Mode

```
┌─────────────────────────────────────────┐
│  Lattice Matrix: 36 bytes               │
│    3x3 matrix, float32, row-major       │
├─────────────────────────────────────────┤
│  Space Group: 2 bytes (uint16)          │
├─────────────────────────────────────────┤
│  Number of Atoms: 4 bytes (uint32)      │
├─────────────────────────────────────────┤
│  Atom Sites (repeated N times):         │
│    ┌─────────────────────────────────┐  │
│    │ Atomic Number: 1 byte (uint8)   │  │
│    │ Coordinates: 12 bytes           │  │
│    │   (x, y, z) as float32          │  │
│    │ Atomic Properties (variable)    │  │
│    │   (see Property Format section) │  │
│    └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Atom Site Base Size**: 1 + 12 = 13 bytes per site (plus properties)

### Molecular Structure (Structure Type = 1)

#### SYMMETRIC Mode

```
┌─────────────────────────────────────────┐
│  Point Group Length: 1 byte (uint8)     │
├─────────────────────────────────────────┤
│  Point Group: N bytes (UTF-8 string)    │
├─────────────────────────────────────────┤
│  Number of Point Group Sites: 1 byte    │
│    (uint8)                              │
├─────────────────────────────────────────┤
│  Point Group Sites (repeated N times):  │
│    ┌─────────────────────────────────┐  │
│    │ Atomic Number: 1 byte (uint8)   │  │
│    │ Multiplicity: 2 bytes (uint16)  │  │
│    │ Coordinates: 12 bytes           │  │
│    │   (x, y, z) as float32          │  │
│    │ Occupancy: 4 bytes (float32)    │  │
│    └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Point Group Site Size**: 1 + 2 + 12 + 4 = 19 bytes per site

#### FULL_ATOMIC Mode

```
┌─────────────────────────────────────────┐
│  Number of Atoms: 4 bytes (uint32)      │
├─────────────────────────────────────────┤
│  Atom Sites (repeated N times):         │
│    ┌─────────────────────────────────┐  │
│    │ Atomic Number: 1 byte (uint8)   │  │
│    │ Coordinates: 12 bytes           │  │
│    │   (x, y, z) as float32          │  │
│    │ Atomic Properties (variable)    │  │
│    │   (see Property Format section) │  │
│    └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Atom Site Base Size**: 1 + 12 = 13 bytes per site (plus properties)

## Property Format

Properties are serialized after the structure data. There are two types: structure-level and atomic-level.

### Structure Properties

```
┌─────────────────────────────────────────┐
│  Number of Built-in Properties: 1 byte  │
│    (uint8)                              │
├─────────────────────────────────────────┤
│  Properties (repeated N times):         │
│    ┌─────────────────────────────────┐  │
│    │ Name Length: 1 byte (uint8)     │  │
│    │ Property Name: N bytes (UTF-8)  │  │
│    │ Data Length: 4 bytes (uint32)   │  │
│    │ Property Data: N bytes          │  │
│    │   (see Property Value Format)   │  │
│    └─────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  Number of Custom Properties: 1 byte    │
│    (uint8)                              │
├─────────────────────────────────────────┤
│  Custom Properties (repeated N times):  │
│    ┌─────────────────────────────────┐  │
│    │ Name Length: 1 byte (uint8)     │  │
│    │ Property Name: N bytes (UTF-8)  │  │
│    │ Value Length: 4 bytes (uint32)  │  │
│    │ Value String: N bytes (UTF-8)   │  │
│    └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Atomic Properties

Atomic properties are attached to individual atoms (only in FULL_ATOMIC mode).

```
┌─────────────────────────────────────────┐
│  Number of Built-in Properties: 1 byte  │
│    (uint8)                              │
├─────────────────────────────────────────┤
│  Properties (repeated N times):         │
│    ┌─────────────────────────────────┐  │
│    │ Name Length: 1 byte (uint8)     │  │
│    │ Property Name: N bytes (UTF-8)  │  │
│    │ Property Data: variable         │  │
│    │   (see Atomic Property Format)  │  │
│    └─────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  Number of Custom Properties: 1 byte    │
│    (uint8)                              │
├─────────────────────────────────────────┤
│  Custom Properties (repeated N times):  │
│    ┌─────────────────────────────────┐  │
│    │ Name Length: 1 byte (uint8)     │  │
│    │ Property Name: N bytes (UTF-8)  │  │
│    │ Value Length: 4 bytes (uint32)  │  │
│    │ Value String: N bytes (UTF-8)   │  │
│    └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Property Value Format

### Scalar Values

#### Float (Structure-level)
- **Format**: `float64` (8 bytes, little-endian)
- **Precision**: Double precision

#### Float (Array element)
- **Format**: `float32` (4 bytes, little-endian)
- **Precision**: Single precision (space-efficient)

#### Integer (Structure-level)
- **Format**: `int64` (8 bytes, little-endian)

#### Integer (Array element)
- **Format**: `int32` (4 bytes, little-endian)

#### Boolean
- **Format**: `bool` (1 byte, `0x00` = false, `0x01` = true)

#### String
```
┌─────────────────────────────────────────┐
│  Length: 1 or 5 bytes                   │
│    If length <= 255: 1 byte (uint8)     │
│    If length > 255: 1 byte (0xFF) +     │
│                     4 bytes (uint32)     │
├─────────────────────────────────────────┤
│  String Data: N bytes (UTF-8)           │
└─────────────────────────────────────────┘
```

#### Tuple (Multi-dimensional)
- Each element: `float32` (4 bytes)
- Total size: `dimension * 4` bytes

### Atomic Property Format

Atomic properties use a count encoding scheme for efficiency:

```
┌─────────────────────────────────────────┐
│  Count Flag: 1 byte (uint8)             │
│    0 = Single value (repeated)          │
│    1-254 = Count (number of values)     │
│    255 = Long count follows             │
├─────────────────────────────────────────┤
│  [If count flag = 255]                  │
│  Long Count: 4 bytes (uint32)           │
├─────────────────────────────────────────┤
│  Values (repeated N times):             │
│    ┌─────────────────────────────────┐  │
│    │ Value Data: variable            │  │
│    │   (see Property Value Format)   │  │
│    └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Count Validation**: For atomic properties, count must be either:
- `1` (single value repeated for all atoms)
- `num_atoms` (one value per atom)

## Hash Calculation

The SHA-256 hash is calculated from the **raw (uncompressed) data** using the same encoding logic as the structure data section, but **excluding**:
- Structure properties
- Formula

The hash includes:
- Structure type and storage mode
- Lattice matrix (for crystals)
- Space group / point group
- All site data (with multiplicity and occupancy for symmetric modes)
- Coordinates (as float32, no rounding)

**Important**: The hash calculation must use **exactly** the same encoding logic as the `encode()` method to ensure consistency.

## Data Type Specifications

### Integer Types

| Type | Size | Range | Format String |
|------|------|-------|---------------|
| uint8 | 1 byte | 0 to 255 | `<B` |
| uint16 | 2 bytes | 0 to 65,535 | `<H` |
| uint32 | 4 bytes | 0 to 4,294,967,295 | `<I` |
| uint64 | 8 bytes | 0 to 18,446,744,073,709,551,615 | `<Q` |
| int8 | 1 byte | -128 to 127 | `<b` |
| int16 | 2 bytes | -32,768 to 32,767 | `<h` |
| int32 | 4 bytes | -2,147,483,648 to 2,147,483,647 | `<i` |
| int64 | 8 bytes | -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807 | `<q` |

### Floating Point Types

| Type | Size | Precision | Format String |
|------|------|-----------|---------------|
| float32 | 4 bytes | ~7 decimal digits | `<f` |
| float64 | 8 bytes | ~15 decimal digits | `<d` |

### Special Values

| Flag | Value | Meaning |
|------|-------|---------|
| LONG_COUNT_FLAG | 0xFF (255) | Long count follows (4 bytes) |
| NULL_FLAG | 0xFE (254) | Null value (reserved) |
| NAN_FLAG | 0xFD (253) | NaN value (reserved) |

## Example: Complete File Structure

### Example 1: Simple Crystal (SYMMETRIC)

```
Header (64 bytes):
  [0-6]    'USIF\x00\x00\x00'
  [7]      5 (version)
  [8-11]   <raw_size> (uint32)
  [12-15]  <compressed_size> (uint32)
  [16]     1 (GZIP)
  [17-48]  <hash> (32 bytes)
  [49-63]  <reserved> (15 bytes, zeros)

Compressed Data (GZIP):
  Raw Data:
    [0]     0 (CRYSTAL)
    [1]     0 (SYMMETRIC)
    [2-37]  <lattice_matrix> (36 bytes, 3x3 float32)
    [38-39] <spacegroup> (2 bytes, uint16)
    [40]    <num_sites> (1 byte, uint8)
    [41-59] <site_1> (19 bytes)
    [60-78] <site_2> (19 bytes)
    ...
    <structure_properties>
    <formula_length> (2 bytes, uint16)
    <formula> (N bytes, UTF-8)
```

### Example 2: Molecule with Properties (FULL_ATOMIC)

```
Header (64 bytes):
  [same as above]

Compressed Data (GZIP):
  Raw Data:
    [0]     1 (MOLECULE)
    [1]     1 (FULL_ATOMIC)
    [2-5]   <num_atoms> (4 bytes, uint32)
    [6-18]  <atom_1> (13 bytes base + properties)
    [19-31] <atom_2> (13 bytes base + properties)
    ...
    <structure_properties>
    <formula_length> (2 bytes, uint16)
    <formula> (N bytes, UTF-8)
```

## Container Format

Container files (`.usifc`) use a different magic byte sequence: `b'USIFC\x00\x00'`

See container implementation for detailed format specification.

## Version History

- **Version 4** (current): Current format with property system
- **Version 3**: Previous version (if any)
- **Version 2**: Previous version (if any)
- **Version 1**: Initial version (if any)

## Compatibility Notes

- Files with version mismatch will log a warning but attempt to decode
- Future versions may add fields to reserved header space
- Property format is extensible through explicit format-version governance

## Implementation Notes

- All multi-byte values use little-endian byte order
- Floating point values use IEEE 754 format
- Strings are UTF-8 encoded
- Coordinates are stored as fractional coordinates for crystals
- Coordinates are stored as Cartesian coordinates for molecules
- Hash is calculated before compression

---

*For architecture overview, see [ARCHITECTURE.md](ARCHITECTURE.md)*

