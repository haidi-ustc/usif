# USIF Architecture Documentation

## Overview

USIF (Universal Structure Interchange Format) is a unified format for storing and exchanging atomic structure data for both periodic (crystals) and non-periodic (molecules) structures. This document provides a high-level architectural overview of the USIF system.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USIF System                              │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Structure  │    │  Properties  │    │   Encoding   │
│    System    │    │    System    │    │    System    │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌──────────────┐
                    │   Container  │
                    │    System    │
                    └──────────────┘
```

## Core Components

### 1. Structure System

The structure system provides the core data model for representing atomic structures.

```
┌─────────────────────────────────────────────────────────────┐
│                    Structure System                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │           USIFStructure (Main Class)               │    │
│  │  - structure_type: CRYSTAL | MOLECULE              │    │
│  │  - storage_mode: SYMMETRIC | FULL_ATOMIC           │    │
│  │  - lattice_matrix (for crystals)                   │    │
│  │  - spacegroup / point_group                        │    │
│  │  - sites: WyckoffSite | PointGroupSite | AtomSite  │    │
│  │  - structure_properties                            │    │
│  │  - formula                                         │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│        ┌─────────────────┼─────────────────┐                │
│        │                 │                 │                │
│        ▼                 ▼                 ▼                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Wyckoff  │    │  Point   │    │   Atom   │             │
│  │   Site   │    │  Group   │    │   Site   │             │
│  │          │    │   Site   │    │          │             │
│  └──────────┘    └──────────┘    └──────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Structure Type Matrix:**

| Structure Type | Storage Mode | Site Type | Use Case |
|---------------|--------------|-----------|----------|
| CRYSTAL | SYMMETRIC | WyckoffSite | Periodic structures with symmetry |
| CRYSTAL | FULL_ATOMIC | AtomSite | Periodic structures, per-atom properties |
| MOLECULE | SYMMETRIC | PointGroupSite | Molecular structures with symmetry |
| MOLECULE | FULL_ATOMIC | AtomSite | Molecular structures, per-atom properties |

### 2. Property System

The property system provides type-safe, validated properties with units and serialization.

```
┌─────────────────────────────────────────────────────────────┐
│                    Property System                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         PropertyDefinition (Type Definition)       │    │
│  │  - name, data_type, dimensions                     │    │
│  │  - is_per_atom (atomic vs structure-level)        │    │
│  │  - units, description                              │    │
│  │  - validation constraints                          │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│        ┌─────────────────┼─────────────────┐                │
│        │                 │                 │                │
│        ▼                 ▼                 ▼                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Property    │  │  Property    │  │  Property    │     │
│  │ Serializer   │  │  Registry    │  │  Containers  │     │
│  │              │  │              │  │              │     │
│  │ - serialize  │  │ - register   │  │ - Atomic     │     │
│  │ - deserialize│  │ - get        │  │ - Structure  │     │
│  │ - validate   │  │ - built-ins  │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Property Types:**

- **Atomic Properties**: Per-atom properties (forces, charges, magnetic moments)
- **Structure Properties**: Structure-level properties (energy, stress, volume)
- **Custom Properties**: User-defined properties with validation

### 3. Encoding System

The encoding system handles binary serialization, compression, and integrity checking.

```
┌─────────────────────────────────────────────────────────────┐
│                    Encoding System                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │              USIF Encoder/Decoder                  │    │
│  │                                                     │    │
│  │  encode(structure) → bytes                         │    │
│  │    ├─ Calculate hash                               │    │
│  │    ├─ Serialize structure data                     │    │
│  │    ├─ Serialize properties                         │    │
│  │    ├─ Compress (optional)                          │    │
│  │    └─ Add header with metadata                     │    │
│  │                                                     │    │
│  │  decode(bytes) → structure                         │    │
│  │    ├─ Read and validate header                     │    │
│  │    ├─ Decompress (if needed)                       │    │
│  │    ├─ Verify hash                                  │    │
│  │    ├─ Deserialize structure data                   │    │
│  │    └─ Deserialize properties                       │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Features:                                                   │
│  - SHA-256 hash for integrity checking                      │
│  - Compression: GZIP (LZMA, BZIP2 planned)                  │
│  - Version tracking                                          │
│  - Error handling and validation                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4. Container System

The container system provides HDF5-like storage for multiple structures.

```
┌─────────────────────────────────────────────────────────────┐
│                    Container System                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         StructureContainer                         │    │
│  │                                                     │    │
│  │  - Store multiple structures in single file        │    │
│  │  - Hierarchical groups (HDF5-like)                 │    │
│  │  - Indexing: hash, formula, properties             │    │
│  │  - Thread-safe operations                          │    │
│  │  - Memory mapping support                          │    │
│  │  - Query and filter structures                     │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│        ┌─────────────────┼─────────────────┐                │
│        │                 │                 │                │
│        ▼                 ▼                 ▼                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │    Indexes   │  │    Groups    │  │    Cache     │     │
│  │              │  │              │  │              │     │
│  │ - hash_index │  │ - hierarchy  │  │ - LRU cache  │     │
│  │ - formula    │  │ - attributes │  │ - thread-safe│     │
│  │ - properties │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### Encoding Flow

```
USIFStructure
    │
    ├─→ Calculate Hash (structure data only)
    │
    ├─→ Serialize Structure
    │   ├─→ Structure type & storage mode
    │   ├─→ Lattice (if crystal)
    │   ├─→ Sites (Wyckoff/PointGroup/Atom)
    │   └─→ Formula
    │
    ├─→ Serialize Properties
    │   ├─→ Structure properties
    │   └─→ Atomic properties (if any)
    │
    ├─→ Compress (optional)
    │
    └─→ Add Header
        ├─→ Magic bytes
        ├─→ Version
        ├─→ Sizes (raw, compressed)
        ├─→ Compression type
        └─→ Hash
```

### Decoding Flow

```
Binary Data
    │
    ├─→ Read Header
    │   ├─→ Validate magic bytes
    │   ├─→ Check version
    │   ├─→ Read sizes
    │   └─→ Extract hash
    │
    ├─→ Decompress (if needed)
    │
    ├─→ Verify Hash
    │
    ├─→ Deserialize Structure
    │   ├─→ Structure type & storage mode
    │   ├─→ Lattice (if crystal)
    │   ├─→ Sites
    │   └─→ Formula
    │
    ├─→ Deserialize Properties
    │   ├─→ Structure properties
    │   └─→ Atomic properties
    │
    └─→ Validate & Return USIFStructure
```

## Module Dependencies

```
┌─────────────┐
│  constants  │ (no dependencies)
└─────────────┘
      │
      ├─→ ┌─────────────┐
      │   │ exceptions  │ (no dependencies)
      │   └─────────────┘
      │
      ├─→ ┌─────────────┐
      │   │    enums    │ (no dependencies)
      │   └─────────────┘
      │
      ├─→ ┌─────────────┐
      │   │    units    │ (no dependencies)
      │   └─────────────┘
      │
      └─→ ┌─────────────────┐
          │   properties    │
          │  - definitions  │
          │  - serializer   │
          │  - registry     │
          │  - atomic       │
          │  - structure    │
          └─────────────────┘
                │
                └─→ ┌─────────────────┐
                    │   structures    │
                    │  - sites        │
                    │  - structure    │
                    └─────────────────┘
                          │
                          ├─→ ┌─────────────┐
                          │   │   encoder   │
                          │   └─────────────┘
                          │
                          ├─→ ┌─────────────┐
                          │   │  converter  │
                          │   └─────────────┘
                          │
                          └─→ ┌─────────────┐
                              │  container  │
                              └─────────────┘
                                    │
                                    └─→ ┌─────────────┐
                                        │    utils    │
                                        │  - optimizer│
                                        │  - benchmark│
                                        └─────────────┘
```

## Key Design Principles

### 1. Modularity

- Clear separation of concerns
- Independent, testable components
- Well-defined interfaces

### 2. Type Safety

- Property definitions with type checking
- Validation at multiple levels
- Type hints throughout

### 3. Efficiency

- Symmetric storage for space efficiency
- Compression support
- Memory mapping for large files
- Caching for performance

### 4. Flexibility

- Support for both crystals and molecules
- Extensible property system
- Custom properties support
- Multiple storage modes

### 5. Reliability

- Hash-based integrity checking
- Comprehensive error handling
- Validation at encoding/decoding
- Thread-safe container operations

## Extension Points

### Adding New Property Types

1. Define property in `PropertyDefinition`
2. Register in `PropertyRegistry`
3. Serialization handled automatically by `PropertySerializer`

### Adding New Storage Modes

1. Add enum value to `StorageMode`
2. Update `USIFStructure._validate_structure()`
3. Update encoder/decoder logic
4. Update site types if needed

### Adding New Compression Algorithms

1. Add enum value to `CompressionType`
2. Implement compression/decompression in `USIF._compress_data()` and `_decompress_data()`
3. Update tests

## Performance Characteristics

- **Encoding**: O(n) where n is number of atoms/sites
- **Decoding**: O(n) with caching support
- **Container Queries**: O(1) for hash lookup, O(k) for formula/property queries
- **Memory**: Efficient with symmetric storage and compression
- **Thread Safety**: Container operations are thread-safe

## Future Enhancements

- Additional compression algorithms (LZMA, BZIP2)
- Spatial indexing for containers
- Similarity search
- Incremental index updates
- Lazy loading for large containers
- Performance monitoring and metrics

---

*For detailed binary format specification, see [BINARY_FORMAT.md](BINARY_FORMAT.md)*
*For import structure analysis, see [IMPORT_STRUCTURE.md](IMPORT_STRUCTURE.md)*

