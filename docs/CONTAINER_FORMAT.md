# USIF Container Format (`.usifc`)

This document describes the current `.usifc` container format implemented by `usif.storage.StructureContainer`, `RecordStore`, `ContainerIndexStore`, and `IndexPersistenceMixin`.

## 1. Purpose

A `.usifc` file stores many complete `.usif` records in one append-friendly file. It adds:

- record-level deduplication by `record_hash`;
- geometry grouping by `geometry_hash`;
- optional user names;
- HDF5-like groups;
- typed structure/group attributes;
- persisted secondary indexes for geometry, formula, and properties;
- append-only, checksummed index generations.

## 2. Top-level layout

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

## 3. Container header

The header is written by `RecordStore.write_header()` and parsed by `ContainerIndexStore.read_container_header()`.

| Offset | Size | Type | Field | Description |
|---:|---:|---|---|---|
| 0 | 7 | bytes | magic | `b"USIFC\x00\x00"` |
| 7 | 1 | uint8 | container_version | current value `1` |
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

## 4. Record storage

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

## 5. Record and geometry identity

Containers use two hashes:

| Hash | Purpose |
|---|---|
| `record_hash` | primary record identity, includes geometry, formula, structure properties, atom properties, and custom properties |
| `geometry_hash` | geometry-only identity used to group records with the same geometry but different properties |

`StructureContainer.add()` deduplicates only identical record hashes. If the same record is added again with a new name, group, or attributes, the record bytes are not written again but the metadata is still recorded.

## 6. Index block layout

Index blocks are written by `ContainerIndexStore.write_index_block()`.

### Index block header

`StructureContainer.INDEX_HEADER_FORMAT` is `<8sQQI4s`.

| Field | Type | Description |
|---|---|---|
| index_magic | 8 bytes | `b"USIFIDX1"` |
| generation | uint64 | monotonic generation value, currently derived from `time.time_ns()` |
| payload_size | uint64 | serialized index payload size |
| checksum | uint32 | CRC32 of the payload |
| reserved | 4 bytes | zero bytes |

### Index block trailer

After the payload, the writer appends:

`b"USIFDONE"`

Readers require this commit marker. A block with a missing commit marker, invalid magic, truncated payload, or checksum mismatch is rejected.

## 7. Index payload layout

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

bytes[8] secondary_index_magic = b"SIDX0001"
uint32   secondary_index_payload_length
bytes    secondary_index_payload_json_utf8
```

The secondary index payload is deterministic JSON and contains `geometry_index`, `formula_index`, and `property_index`. Property index keys are JSON-normalized and recursively tuple-encoded when needed so scalar, vector, tensor, and dotted custom-property queries can be answered without decoding every record.

## 8. Group hierarchy payload

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

## 9. Attribute value encoding

Structure and group attributes are encoded by `AttributeCodecMixin` as JSON UTF-8 bytes. The codec preserves JSON-compatible types such as strings, numbers, booleans, `null`, lists, and dictionaries. Scientific values are normalized when necessary by the JSON default function.

The container no longer uses lossy `str(value)` attribute persistence.

## 10. Reading and recovery

Normal open path:

```text
read 64-byte header
read index block at header.index_offset
validate magic, payload size, CRC32, commit marker
deserialize primary/name/group/attribute indexes
load persisted geometry/formula/property secondary indexes
```

If the header index offset is invalid, `ContainerIndexStore.find_latest_valid_index_offset()` performs a bounded streaming scan in 1 MiB chunks to find the newest valid index block. It does not materialize the entire container file.

## 11. Validation

`StructureContainer.validate(level="index")` returns a `ContainerValidationResult`. Validation levels are explicit:

| Level | Checks | Cost |
|---|---|---|
| `index` | index references, groups, attributes, chunk locations | no record reads |
| `records` | `index` plus record byte ranges and USIF headers | bounded record reads, no full decode |
| `full` | `records` plus full structure decode and record-hash verification | strongest and slowest |

The older `decode_records=True` convenience flag maps to `level="full"`; new code should use `level`.

## 12. Threading model

The container uses:

- `_index_lock` for index and metadata updates;
- `_file_lock` for record/index writes;
- `StructureCache` for decoded-record caching;
- a prefetch worker for batch/prefetch workflows.

Thread safety is intended for concurrent reads and guarded in-process writes. Cross-process concurrent writes are not supported.
