# USIF Binary Format (`.usif`)

This document specifies the current single-structure `.usif` record format implemented by `usif.encoder.USIF` and `usif.format.binary`.

## 1. Version and byte order

| Item | Value |
|---|---|
| Binary record format version | `5` (`usif.version.FORMAT_VERSION`) |
| Endianness | little-endian |
| Header size | 64 bytes |
| Supported compression values | `0 = NONE`, `1 = GZIP` |
| Header identity hash | geometry hash of decoded `USIFStructure` |

All integer and floating-point primitives use the explicit little-endian formats in `usif.constants.BinaryFormat`.

## 2. File layout

```text
+------------------------------+
| 64-byte fixed header          |
+------------------------------+
| compressed payload bytes      |
+------------------------------+
```

The payload is the serialized structure body. The header records both the uncompressed payload size and the compressed payload size. On decode, USIF checks the compressed byte count, decompresses to the declared raw size, decodes the body, and validates the decoded geometry hash against the header geometry hash.

## 3. Header layout

The header is implemented by `usif.format.binary.header.USIFHeader`.

| Offset | Size | Type | Field | Description |
|---:|---:|---|---|---|
| 0 | 7 | bytes | magic | `b"USIF\x00\x00\x00"` |
| 7 | 1 | uint8 | version | current value `5` |
| 8 | 4 | uint32 | raw_size | uncompressed payload byte length |
| 12 | 4 | uint32 | compressed_size | compressed payload byte length |
| 16 | 1 | uint8 | compression_type | `0 = NONE`, `1 = GZIP` |
| 17 | 32 | bytes | geometry_hash | SHA-256 geometry hash from `calculate_geometry_hash()` |
| 49 | 15 | bytes | reserved | zero padding to 64 bytes |

Defensive limits are enforced before allocation. Current limits include 512 MiB for raw and compressed payloads, 10,000,000 atoms, 255 symmetric sites, 255 known properties, 255 custom properties, and 64 MiB per property value.

## 4. Uncompressed payload layout

The uncompressed payload is implemented by `StructureBinaryCodec.encode_body()` / `decode_body()`.

```text
uint8 structure_type        # 0 = CRYSTAL, 1 = MOLECULE
uint8 storage_mode          # 0 = SYMMETRIC, 1 = FULL_ATOMIC
structure-specific body
uint32 structure_property_section_length
bytes  structure_property_section
uint16 formula_utf8_length
bytes  formula_utf8
```

The entire payload must be consumed during decode; trailing bytes are rejected.

## 5. Crystal body

### Crystal + symmetric storage

```text
float32[9] lattice_matrix   # 3x3 row-major matrix, 36 bytes
uint16     spacegroup
uint8      wyckoff_site_count
repeated wyckoff_site_count times:
  uint8      atomic_number
  uint16     multiplicity
  float32[3] fractional_coords
  float32    occupancy
```

### Crystal + full-atomic storage

```text
float32[9] lattice_matrix   # 3x3 row-major matrix, 36 bytes
uint16     spacegroup
uint32     atom_count
repeated atom_count times:
  uint8      atomic_number
  float32[3] fractional_coords
  property section for this atom
```

Per-atom property sections are present only for full-atomic storage.

## 6. Molecule body

### Molecule + symmetric storage

```text
uint8      point_group_utf8_length
bytes      point_group_utf8
uint8      point_group_site_count
repeated point_group_site_count times:
  uint8      atomic_number
  uint16     multiplicity
  float32[3] cartesian_coords
  float32    occupancy
```

### Molecule + full-atomic storage

```text
uint32     atom_count
repeated atom_count times:
  uint8      atomic_number
  float32[3] cartesian_coords
  property section for this atom
```

Crystal coordinates are fractional; molecule coordinates are Cartesian.

## 7. Property section layout

Property sections are implemented by `usif.format.binary.property_codec.PropertyCodec` and `usif.properties.serializer.PropertySerializer`.

Each structure property section and each atomic property section has the same high-level shape:

```text
uint8 known_property_count
repeated known_property_count times:
  uint8 property_name_utf8_length
  bytes property_name_utf8
  uint32 property_value_byte_length
  bytes property_value
uint8 custom_property_count
repeated custom_property_count times:
  uint8 custom_name_utf8_length
  bytes custom_name_utf8
  uint32 custom_value_byte_length
  bytes custom_value_utf8
```

Known properties are selected from the active `PropertyRegistry`. Structure sections include structure properties only; atomic sections include per-atom properties only.

Custom values are stored as UTF-8 text. JSON-compatible custom values are encoded with the prefix `__USIF_JSON__:` followed by compact JSON. Non-prefixed strings are decoded as plain strings.

## 8. Property value encoding

`PropertySerializer` encodes values according to their `PropertyDefinition`.

| Property definition | Encoding |
|---|---|
| scalar `float` | `float64` |
| scalar `int` | `int64` |
| scalar `bool` | one byte boolean |
| scalar `str` | length-prefixed UTF-8; 1-byte length or `255` + uint32 length |
| tuple/list with dimensions | repeated numeric elements using the definition's scalar numeric format |
| per-atom property | count byte first, then one or more encoded elements |

Per-atom count encoding uses:

| Count byte | Meaning |
|---:|---|
| `0` | one encoded value; repeat for all atoms when a larger atom count is supplied |
| `1..254` | that many encoded values follow |
| `255` | uint32 count follows, then that many encoded values |

When decoding a single `AtomSite`, `num_atoms=1` is used for that atom's property section.

## 9. Integrity and version policy

`USIF.decode()` validates:

1. magic bytes;
2. compression type;
3. payload size declarations;
4. decompressed raw size;
5. structure/body bounds;
6. property bounds and registry-defined values;
7. geometry hash against the decoded structure.

A header version mismatch is rejected with `CorruptedDataError`. Current decoders only accept the declared `FORMAT_VERSION` for the physical layout they implement.
