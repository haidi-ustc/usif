# File formats of USIF 0.8 and earlier (read-only)

USIF 0.9 reads these files but no longer writes them:

* `.usif` records of formats 5 and 6 are read by `usif.read()` through `usif.upgrade.format6`;
* `.usifc` version-2 containers are read by `usif.upgrade.open_container_v2()` and converted with
  `Dataset.import_v2()`.

The readers are frozen. Their notes on how 0.8 data maps to a `Structure` are:

* every 0.8 structure property, per-atom property and custom value is kept, with its unit;
  the internal key `__usif_symmetry_metadata__` is dropped;
* a built-in per-atom property (`force`, `charge`, `magmom`, `velocity`) that only some atoms carry is stored
  as zero on the others, with a boolean `<name>_present` array and a warning;
* symmetric records are expanded exactly as 0.8 did, and atoms are ordered by atomic number, then coordinates;
  occupancies other than 1 become an `occupancy` array;
* the stored SHA-256 geometry hash is recomputed and checked for every record;
* properties defined by a custom 0.8 `PropertyRegistry` cannot be decoded and are skipped with a warning.

The sections below are the 0.8 specifications, unchanged except for headings and opening sentences.

## Record formats 5 and 6 (`.usif`)

This is the record layout USIF 0.7 and 0.8 wrote. `usif.upgrade.format6` reads it.

### 1. Version and byte order

| Item | Value |
|---|---|
| Binary record format version | `6` (`usif.version.FORMAT_VERSION`); format `5` is still decoded |
| Endianness | little-endian |
| Header size | 64 bytes |
| Supported compression values | `0 = NONE`, `1 = GZIP` |
| Header identity hash | geometry hash of decoded `USIFStructure` |

All integer and floating-point primitives use the explicit little-endian formats in `usif.constants.BinaryFormat`.

### 2. File layout

```text
+------------------------------+
| 64-byte fixed header          |
+------------------------------+
| compressed payload bytes      |
+------------------------------+
```

The payload is the serialized structure body. The header records both the uncompressed payload size and the compressed payload size. On decode, USIF checks the compressed byte count, decompresses to the declared raw size, decodes the body, and validates the decoded geometry hash against the header geometry hash.

### 3. Header layout

The header is implemented by `usif.format.binary.header.USIFHeader`.

| Offset | Size | Type | Field | Description |
|---:|---:|---|---|---|
| 0 | 7 | bytes | magic | `b"USIF\x00\x00\x00"` |
| 7 | 1 | uint8 | version | `6` when written; `5` or `6` accepted on decode |
| 8 | 4 | uint32 | raw_size | uncompressed payload byte length |
| 12 | 4 | uint32 | compressed_size | compressed payload byte length |
| 16 | 1 | uint8 | compression_type | `0 = NONE`, `1 = GZIP` |
| 17 | 32 | bytes | geometry_hash | SHA-256 geometry hash from `calculate_geometry_hash()` |
| 49 | 15 | bytes | reserved | zero padding to 64 bytes |

Defensive limits are enforced before allocation. Current limits include 512 MiB for raw and compressed payloads, 10,000,000 atoms and symmetric sites (255 symmetric sites in format 5), 255 known properties, 255 custom properties, and 64 MiB per property value.

### 4. Uncompressed payload layout

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

### 5. Crystal body

#### Crystal + symmetric storage

```text
float32[9] lattice_matrix   # 3x3 row-major matrix, 36 bytes
uint16     spacegroup       # 1..230, informational; hall_number defines the operations
uint16     hall_number      # spglib Hall number, 1..530
uint8      setting_flags    # bit 0: P is identity (omitted); bit 1: p is zero (omitted)
float64[9] P                # only when bit 0 is clear; row-major
float64[3] p                # only when bit 1 is clear
uint32     wyckoff_site_count
repeated wyckoff_site_count times:
  uint8      atomic_number
  uint32     multiplicity
  float32[3] fractional_coords   # in the stored cell, not the standard cell
  float32    occupancy
```

`(P, p)` maps stored-cell fractional coordinates to the standard setting of `hall_number`: `x_std = P x + p`. Expansion applies the Hall-number operations `(R, t)` in the stored basis as `W = P^-1 R P`, `w = P^-1 (R p + t - p)`, plus the lattice translations spanned by the columns of `P^-1` (needed when the stored cell is a supercell of the standard cell). Orbit images closer than 1e-5 in fractional coordinates are merged. Expanded atoms are ordered by atomic number, then coordinates. Unknown `setting_flags` bits are rejected.

Format-5 symmetric crystals store only `spacegroup` (no Hall number, flags, `P` or `p`), a `uint8` site count and `uint16` multiplicities. They are expanded in the setting they were written with, through the frozen space-group -> Hall table in `usif/symmetry/tables.py`, with `P = I` and `p = 0`.

#### Crystal + full-atomic storage

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

### 6. Molecule body

#### Molecule + symmetric storage

```text
uint8      point_group_utf8_length
bytes      point_group_utf8
uint32     point_group_site_count     # uint8 in format 5
repeated point_group_site_count times:
  uint8      atomic_number
  uint32     multiplicity             # uint16 in format 5
  float32[3] cartesian_coords
  float32    occupancy
```

#### Molecule + full-atomic storage

```text
uint32     atom_count
repeated atom_count times:
  uint8      atomic_number
  float32[3] cartesian_coords
  property section for this atom
```

Crystal coordinates are fractional; molecule coordinates are Cartesian.

USIF 0.8 writes molecules only as full-atomic records. Symmetric molecule records (format 5) are still decoded and expanded with the frozen point-group operation tables in `usif/symmetry/tables.py`.

### 7. Property section layout

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

### 8. Property value encoding

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

### 9. Integrity and version policy

`USIF.decode()` validates:

1. magic bytes;
2. compression type;
3. payload size declarations;
4. decompressed raw size;
5. structure/body bounds;
6. property bounds and registry-defined values;
7. geometry hash against the decoded structure.

Header versions other than `5` and `6` are rejected with `CorruptedDataError`. The decoder selects the body layout from the header version, so format-5 files and containers holding format-5 records stay readable; encoders always write `FORMAT_VERSION`.

### 10. Hashes

The header `geometry_hash` covers the lattice, storage mode, space group and sites as float32 values. For format-6 symmetric crystals with a non-default setting (any `P != I` or `p != 0`), the Hall number, `P` and `p` are included as well; records in the default setting hash exactly as format 5 did, so their geometry hashes are unchanged.

## Container version 2 (`.usifc`)

This is the container layout USIF 0.8 wrote. `usif.upgrade.container_v2` reads it.

### 1. Purpose

A `.usifc` file stores many complete `.usif` records in one append-friendly file. It adds:

- record-level deduplication by `record_hash`;
- geometry grouping by `geometry_hash`;
- optional user names;
- HDF5-like groups;
- typed structure/group attributes;
- persisted secondary indexes for geometry, formula, and properties;
- append-only, checksummed index generations.

### 2. Top-level layout

```text
+------------------------------+
| 64-byte container header      |
+------------------------------+
| encoded .usif records         |
| optional chunk padding        |
+------------------------------+
| index block generation N      |
+------------------------------+
| index block generation N+1    |
+------------------------------+
| ...                          |
+------------------------------+
```

Record data is append-only. Index blocks are appended at close. The fixed container header points to the latest committed index generation.

### 3. Container header

The header is written by `RecordStore.write_header()` and parsed by `ContainerIndexStore.read_container_header()`.

| Offset | Size | Type | Field | Description |
|---:|---:|---|---|---|
| 0 | 7 | bytes | magic | `b"USIFC\x00\x00"` |
| 7 | 1 | uint8 | container_version | current value `2` |
| 8 | 4 | uint32 | structure_count | number of stored unique records |
| 12 | 8 | uint64 | data_offset | first record area offset, currently `64` |
| 20 | 8 | uint64 | index_offset | byte offset of latest committed index block, or `0` |
| 28 | 8 | uint64 | group_offset | reserved, currently `0` |
| 36 | 8 | uint64 | attribute_offset | reserved, currently `0` |
| 44 | 1 | uint8 | compression_type | compression value passed to `USIF` for records |
| 45 | 1 | uint8 | use_chunking | `1` in current writer |
| 46 | 8 | uint64 | created_at | Unix timestamp |
| 54 | 8 | uint64 | updated_at | Unix timestamp |
| 62 | 2 | bytes | reserved | zero padding to 64 bytes |

### 4. Record storage

Each record is a complete `.usif` byte sequence produced by `USIF.encode()`. The container does not reinterpret the record body during low-level storage.

The in-memory primary index maps:

```text
record_hash -> (chunk_id: uint32, chunk_offset: uint64, record_size: uint32)
```

`RecordStore` uses a 64 MiB chunk size. Actual file offset is:

```text
actual_offset = chunk_id * chunk_size + chunk_offset
```

When a record does not fit in the remaining space of a chunk, padding is inserted and the record starts in the next chunk. `use_mmap=True` is used when possible; otherwise ordinary file reads/writes are used.

### 5. Record and geometry identity

Containers use two hashes:

| Hash | Purpose |
|---|---|
| `record_hash` | primary record identity, includes geometry, formula, structure properties, atom properties, and custom properties |
| `geometry_hash` | geometry-only identity used to group records with the same geometry but different properties |

`StructureContainer.add()` deduplicates only identical record hashes. If the same record is added again with a new name, group, or attributes, the record bytes are not written again but the metadata is still recorded.

### 6. Index block layout

Index blocks are written by `ContainerIndexStore.write_index_block()`.

#### Index block header

`StructureContainer.INDEX_HEADER_FORMAT` is `<8sQQI4s`.

| Field | Type | Description |
|---|---|---|
| index_magic | 8 bytes | `b"USIFIDX2"` |
| generation | uint64 | monotonic generation value, currently derived from `time.time_ns()` |
| payload_size | uint64 | serialized index payload size |
| checksum | uint32 | CRC32 of the payload |
| reserved | 4 bytes | zero bytes |

#### Index block trailer

After the payload, the writer appends:

`b"USIFDONE"`

Readers require this commit marker. A block with a missing commit marker, invalid magic, truncated payload, or checksum mismatch is rejected.

### 7. Index payload layout

The payload is serialized by `IndexPersistenceMixin._serialize_indexes()` and decoded by `_deserialize_indexes_from_payload()`.

```text
uint32 record_index_count
repeated record_index_count times:
  uint16 record_hash_length
  bytes  record_hash_utf8
  uint32 chunk_id
  uint64 chunk_offset
  uint32 record_size

uint32 name_index_count
repeated name_index_count times:
  uint16 name_length
  bytes  name_utf8
  uint16 record_hash_length
  bytes  record_hash_utf8

uint32 structure_attribute_entry_count
repeated structure_attribute_entry_count times:
  uint16 structure_name_length
  bytes  structure_name_utf8
  uint16 attribute_pair_count
  repeated attribute_pair_count times:
    uint16 attribute_name_length
    bytes  attribute_name_utf8
    uint32 attribute_value_length
    bytes  attribute_value_json_utf8

uint32 group_hierarchy_length
bytes  group_hierarchy_payload

bytes[8] secondary_index_magic = b"SIDX0002"
uint32   secondary_index_payload_length
bytes    secondary_index_payload_json_utf8
```

The secondary index payload is deterministic JSON and contains `geometry_index`, `formula_index`, and `property_index`. Property index keys are JSON-normalized and recursively tuple-encoded when needed so scalar, vector, tensor, and dotted custom-property queries can be answered without decoding every record.

### 8. Group hierarchy payload

The group hierarchy is a recursive tree of `USIFGroup` objects:

```text
uint16 group_name_length
bytes  group_name_utf8
uint32 group_structure_count
repeated group_structure_count times:
  uint16 structure_name_length
  bytes  structure_name_utf8
  uint16 record_hash_length
  bytes  record_hash_utf8
uint16 group_attribute_count
repeated group_attribute_count times:
  uint16 attribute_name_length
  bytes  attribute_name_utf8
  uint32 attribute_value_length
  bytes  attribute_value_json_utf8
uint32 subgroup_count
repeated subgroup_count times:
  nested group payload
```

The root group has name `/`. Child paths are represented in memory with slash-delimited absolute paths such as `/crystals/oxides/`.

### 9. Attribute value encoding

Structure and group attributes are encoded by `AttributeCodecMixin` as JSON UTF-8 bytes. The codec preserves JSON-compatible types such as strings, numbers, booleans, `null`, lists, and dictionaries. Scientific values are normalized when necessary by the JSON default function.

The container no longer uses lossy `str(value)` attribute persistence.

### 10. Reading and recovery

Normal open path:

```text
read 64-byte header
read index block at header.index_offset
validate magic, payload size, CRC32, commit marker
deserialize primary/name/group/attribute indexes
load persisted geometry/formula/property secondary indexes
```

If the header index offset is invalid, `ContainerIndexStore.find_latest_valid_index_offset()` performs a bounded streaming scan in 1 MiB chunks to find the newest valid index block. It does not materialize the entire container file.

### 11. Validation

`StructureContainer.validate(level="index")` returns a `ContainerValidationResult`. Validation levels are explicit:

| Level | Checks | Cost |
|---|---|---|
| `index` | index references, groups, attributes, chunk locations | no record reads |
| `records` | `index` plus record byte ranges and USIF headers | bounded record reads, no full decode |
| `full` | `records` plus full structure decode and record-hash verification | strongest and slowest |

Validation uses the explicit `level` argument only: `"index"`, `"records"`, or `"full"`.

### 12. Threading model

The container uses:

- `_index_lock` for index and metadata updates;
- `_file_lock` for record/index writes;
- `StructureCache` for decoded-record caching;
- a prefetch worker for batch/prefetch workflows.

Thread safety is intended for concurrent reads and guarded in-process writes. Cross-process concurrent writes are not supported.

### Container introspection and query notes

Current containers expose public introspection helpers built from persisted indexes:

- `list_names()` returns named structure aliases.
- `list_formulas()` returns formulas present in the formula index.
- `list_properties()` returns indexed property and dotted custom-property names.
- `list_groups()` returns normalized public group paths.
- `stats()` returns the canonical statistics schema with counts, file/index sizes, indexed property names, formula lists, group paths, compression ratio, and nested cache/storage details without decoding stored records.

Queries can now use `has_property`, `property_range=(name, min, max)`, and
`custom={"metadata.family": "hydride"}`. These filters resolve against the
persisted secondary indexes and then decode only the matched records.
