# Records and JSON documents

A single structure is stored either as a binary `.usif` record (format 7) or as a JSON document (`usif.structure.json.v2`). Both keep every value, dtype and unit, and both round-trip exactly with the default options.

```python
import usif
from usif import Cell, Structure

s = Structure.from_fractional(["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(5.64),
                              properties={"energy": -6.8})
usif.write(s, "nacl.usif")               # binary record
usif.write(s, "nacl.json")               # JSON document
assert usif.read("nacl.usif") == s
assert usif.read("nacl.json") == s

data = usif.encode(s)                    # record bytes
assert usif.decode(data) == s
```

`usif.write(s, path, **options)` takes the encoding options below for `.usif` and `indent` for `.json`. Writes replace the target atomically.

## Record options

| Option | Values | Default | Effect |
|---|---|---|---|
| `compression` | `none`, `zlib`, `lzma`, `zstd` | `zlib` | Payload compression. `zstd` needs the `zstandard` package. |
| `level` | int or `None` | codec default | Compression level. |
| `precision` | `f64`, `f32` | `f64` | Positions as float64 (exact) or float32 (smaller; positions are rounded to float32). The cell and properties are unaffected. |
| `symmetry` | `off`, `auto` | `off` | `auto` stores the asymmetric unit (spglib Hall number, setting transformation, representatives and the original atom order) instead of all positions. |

The defaults are exact. `symmetry="auto"` is applied only when every condition holds:

- the structure is periodic along all three axes and has no per-atom arrays;
- re-expanding the asymmetric unit reproduces every atom, in the original order, within 1e-5 Å;
- the resulting record is smaller than the plain one.

Otherwise the record silently stores all positions; `RecordInfo.symmetric` tells you which form was written. Symmetric storage pays off for large, symmetric cells.

## Identity hashes

`usif.codec.encode_with_info()` and `decode_with_info()` return the structure or bytes together with a `RecordInfo` (`record_hash`, `geometry_hash`, `natoms`, `compression`, `raw_size`, `stored_size`, `symmetric`):

- `record_hash`: BLAKE2b-256 of the uncompressed payload, i.e. the whole structure including properties. Use it as the identity of the complete record; datasets deduplicate records by it.
- `geometry_hash`: BLAKE2b-256 of the atom, cell and position sections only. Use it to find the same geometry with different calculated properties.

Encoding is canonical (fixed section order, columns sorted by name, canonical JSON), so equal structures encoded with equal options give identical bytes and hashes. The hashes depend on `precision` and `symmetry`, but not on `compression`.

## Worked example

[`examples/01_structures_and_records.py`](../../examples/01_structures_and_records.py) builds a rock-salt cell with properties, compares the encoding options on a 216-atom supercell and checks the two hashes:

```python
import numpy as np
from usif import Cell, Structure
from usif.codec import encode_with_info

ROCKSALT = [
    [0, 0, 0], [0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0],
    [0.5, 0.5, 0.5], [0.5, 0, 0], [0, 0.5, 0], [0, 0, 0.5],
]
nacl = Structure.from_fractional([11] * 4 + [17] * 4, ROCKSALT, Cell.cubic(5.64))
nacl.properties["energy"] = -27.2
nacl.properties["calculation"] = {"code": "VASP", "encut": 520}

# 3x3x3 supercell: symmetry="auto" stores 2 atoms instead of 216
grid = np.array(np.meshgrid(*[range(3)] * 3)).reshape(3, -1).T
frac = ((np.array(ROCKSALT)[None] + grid[:, None]) / 3).reshape(-1, 3)
supercell = Structure.from_fractional(np.tile(nacl.numbers, 27), frac, Cell.cubic(3 * 5.64))
for options in ({}, {"symmetry": "auto"}, {"precision": "f32"}, {"compression": "lzma"}):
    data, info = encode_with_info(supercell, **options)
    print(f"{str(options):28} {len(data):6d} bytes  symmetric={info.symmetric}")

# Same geometry, different content
relaxed = nacl.copy()
relaxed.arrays["force"] = np.zeros((8, 3))
a = encode_with_info(nacl)[1]
b = encode_with_info(relaxed)[1]
assert a.geometry_hash == b.geometry_hash
assert a.record_hash != b.record_hash
```

## Safety

`decode` verifies the 8-byte BLAKE2b digest of the stored payload before decompressing it, caps decompression at the size the header declares, bounds-checks every read and limits the payload size (`max_size`, 2 GiB by default). Decoding is strict: it accepts only canonically encoded payloads, so re-encoding a decoded record with the same options gives the same bytes.

Errors are `usif.FormatError` (truncated or malformed data), `usif.ChecksumError` (corrupted data) or `usif.UnsupportedVersionError` (a version this reader does not know):

```python
import usif

data = bytearray(usif.encode(usif.Structure(["H"], [[0, 0, 0]])))
data[-1] ^= 0xFF
try:
    usif.decode(bytes(data))
except usif.ChecksumError as exc:
    print(exc)
```

`usif.read` also reads format-5/6 records written by USIF 0.8 and earlier; `usif.decode` reads only format 7 (see [Upgrading USIF 0.8 files](upgrading.md)). The byte layout is specified in [BINARY_FORMAT.md](../BINARY_FORMAT.md).

## JSON documents

Files ending in `.json` or `.usif.json` hold one structure:

```json
{
  "schema": "usif.structure.json.v2",
  "numbers": [11, 17],
  "positions": [[0.0, 0.0, 0.0], [2.82, 2.82, 2.82]],
  "cell": {"matrix": [[5.64, 0.0, 0.0], [0.0, 5.64, 0.0], [0.0, 0.0, 5.64]], "pbc": [true, true, true]},
  "arrays": {},
  "properties": {"energy": {"dtype": "<f8", "unit": "eV", "value": -6.8}}
}
```

`cell` is `null` for molecules. Every property entry has `dtype` (a NumPy dtype string or `"json"`), `unit` and `value`. Floats are written with full precision, so reading the document back gives an equal structure.

```python
from usif.codec import jsondoc

text = jsondoc.dumps(s)                  # indent=2 by default
assert jsondoc.loads(text) == s
document = jsondoc.to_document(s)        # a dict
assert jsondoc.from_document(document) == s
usif.write(s, "nacl.json", indent=None)  # compact single line
```

A document with another `schema` value (including the 0.8 schema `usif.structure.json.v1`) is rejected with `FormatError`.
