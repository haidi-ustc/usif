# Binary `.usif` Format

The `.usif` file stores one complete USIF structure record.

- Magic: `b"USIF\x00\x00\x00"`
- Binary record format version: `6` (format `5` records remain readable)
- Hash in record header: `geometry_hash`
- Record hash: computed over the canonical (encoded and decoded) logical record, including properties, and used by `.usifc` deduplication
- Compression types: `0 = NONE`, `1 = GZIP`

The binary format is implemented by `usif.encoder.USIF` and focused modules under `usif.format.binary`.

## Typical flow

```python
from usif import USIF

codec = USIF()
data = codec.encode(structure)
decoded, geometry_hash = codec.decode(data)
```

Use `docs/BINARY_FORMAT.md` for the normative low-level layout.
