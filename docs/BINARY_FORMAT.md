# The `.usif` record, format 7

A record holds one structure: atoms, positions, an optional cell, per-atom arrays and structure
properties. It is the unit stored in `.usif` files and in every row of a `.usifc` dataset.
`usif.codec.record` implements it.
Records written by USIF 0.8 and earlier (formats 5 and 6) are described in
[FORMATS_0_8.md](FORMATS_0_8.md).

All integers and floats are little-endian. Arrays are stored in C order.

## 1. Layout

```text
+----------------------+
| header, 40 bytes     |
+----------------------+
| stored payload       |  compressed (or not) sequence of sections
+----------------------+
```

### Header

| Offset | Size | Field | Value |
|---:|---:|---|---|
| 0 | 8 | magic | `89 55 53 49 46 0D 0A 1A` (`\x89USIF\r\n\x1a`) |
| 8 | 2 | version | `7` |
| 10 | 2 | flags | `0`; a reader rejects any set bit |
| 12 | 1 | compression | codec id: `0` none, `1` zlib, `2` lzma (xz), `3` zstd |
| 13 | 3 | reserved | zero |
| 16 | 8 | raw_size | payload size after decompression |
| 24 | 8 | stored_size | payload size as stored |
| 32 | 8 | digest | BLAKE2b-64 of the stored payload |

`digest` is the 8-byte BLAKE2b digest (`digest_size=8`) of the *stored* payload bytes. The magic's
first byte is non-ASCII and it contains CR LF and Ctrl-Z, so text-mode transfers and truncation to 7
bits are detected (the PNG convention).

### Sections

The decompressed payload is a sequence of sections:

```text
tag    4 bytes ASCII
size   u64
body   size bytes
```

Sections appear in this order: `ATOM`, `CELL` (optional), exactly one of `POSN` and `SYMM`, `ARRS`
(optional), `PROP` (optional). A tag that starts with a lower-case letter is *ancillary*: readers
that do not know it skip it, so later versions can add optional data without a format change. Any
other unknown tag, a duplicate, a missing required section or a different order is an error.

| Tag | Body |
|---|---|
| `ATOM` | `natoms u32`, then `natoms` atomic numbers (`u8`, 1..118) |
| `CELL` | `pbc u8` (bit *i* set = periodic along lattice vector *i*), lattice `f64[3][3]` (rows are lattice vectors, Å) |
| `POSN` | `dtype u8` (`11` = f64, `10` = f32), Cartesian positions `[natoms][3]` (Å) |
| `SYMM` | the asymmetric unit, see section 3 |
| `ARRS` | per-atom arrays: a column block (section 2) whose columns all have `natoms` rows |
| `PROP` | structure properties: a column block |

## 2. Column blocks

```text
count   u32
repeated count times, sorted by name (byte order of the UTF-8 name):
  name    u16 length + UTF-8 (1..255 bytes, no control characters)
  unit    u16 length + UTF-8 (normalised spelling, "" for none)
  dtype   u8
  if dtype == 0 (JSON):
    length  u64
    text    canonical JSON (sorted keys, no whitespace, no NaN/Infinity)
  else:
    ndim    u8 (<= 8)
    shape   u64[ndim]
    data    product(shape) items of dtype
```

| Code | dtype | Code | dtype |
|---:|---|---:|---|
| 0 | JSON | 6 | uint8 |
| 1 | bool | 7 | uint16 |
| 2 | int8 | 8 | uint32 |
| 3 | int16 | 9 | uint64 |
| 4 | int32 | 10 | float32 |
| 5 | int64 | 11 | float64 |

Numeric values must be finite. Per-atom columns have `shape[0] == natoms`. Decoding validates every
column through the structure's `Schema`, as assignment does, so a record cannot hold a value the
model would reject.

## 3. The `SYMM` section

`symmetry="auto"` stores the asymmetric unit when that reproduces every atom within 1e-5 Å (in
Cartesian space, without wrapping, so atoms outside the cell are never "repaired"), the structure has
a full 3-D periodic cell and no per-atom arrays, and the stored record comes out smaller than with
`POSN`. Otherwise the record uses `POSN`.

```text
hall      u16     spglib Hall number (1..530)
flags     u8      bit 0: P is the identity (omitted); bit 1: p is zero (omitted);
                  bit 2: an atom order follows; other bits must be 0
P         f64[3][3]   only when bit 0 is clear
p         f64[3]      only when bit 1 is clear
nreps     u32
numbers   u8[nreps]
mult      u32[nreps]  sum == natoms
reps      f64[nreps][3]   fractional coordinates in the stored cell
order     only when bit 2 is set: width u8 (2 or 4), then u16/u32[natoms]
```

`(P, p)` maps stored-cell fractional coordinates to the standard setting of the Hall number:
`x_std = P x + p`. In the stored basis the operations are `W = P⁻¹ R P` and
`w = P⁻¹ (R p + t − p)`, plus the lattice translations spanned by the columns of `P⁻¹` (a stored
supercell). Each representative expands to its distinct images, wrapped to [0, 1). The expanded
atoms are sorted by atomic number, then by wrapped fractional coordinates rounded to 1e-8; when
`order` is present, atom *i* of the structure is canonical atom `order[i]`. The expanded numbers
must equal the `ATOM` section.

## 4. Identity

| Hash | Covers | Meaning |
|---|---|---|
| `record_hash` | BLAKE2b-256 of the raw payload | the stored content: same hash, same structure, same encoding |
| `geometry_hash` | BLAKE2b-256 of the payload up to the end of `POSN`/`SYMM` | atoms, cell and positions only |
| header `digest` | BLAKE2b-64 of the stored payload | corruption check, verified before decompression |

Encoding is deterministic, so equal structures encoded with equal options give identical bytes and
hashes. The options are part of the content: the same structure stored with `precision="f32"` or as
`SYMM` has a different `record_hash`. A dataset uses one set of options, so deduplication inside a
dataset is exact.

## 5. Decoding limits

A reader:

1. checks magic, version, flags and reserved bytes;
2. rejects records whose `raw_size` exceeds its limit (2 GiB by default, `max_size=`) before allocating;
3. requires the input to be exactly `40 + stored_size` bytes;
4. verifies the digest, then decompresses with output bounded to `raw_size` and requires exactly
   `raw_size` bytes;
5. bounds-checks every read and requires each section to be fully consumed.

Every failure raises `usif.errors.FormatError`; digest mismatches raise its subclass `ChecksumError`.

## 6. Versioning

The header `version` changes only when a change cannot be expressed with an ancillary section or a
new column (see [FORMAT_VERSIONING.md](FORMAT_VERSIONING.md)). Writers always write the current
version; `usif.read()` also reads formats 5 and 6.
