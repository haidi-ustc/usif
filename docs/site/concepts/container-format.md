# Container `.usifc` Format

`.usifc` stores many complete `.usif` records in one append-oriented container.

## Key ideas

| Concept | Meaning |
|---|---|
| `record_hash` | hash of the complete encoded record; used for exact deduplication |
| `geometry_hash` | hash of geometry only; groups records with same geometry but different properties |
| `ContainerIndexStore` | reads/writes index manifest, CRC, commit marker, and bounded recovery scans |
| `RecordStore` | manages file access, mmap fallback, record reads/writes, and chunk allocation |

## Query and validation

```python
with StructureContainer("materials.usifc", mode="r") as c:
    c.list_formulas()
    c.query(formula="NaCl", has_property="energy")
    c.query(property_range=("energy", -20.0, -1.0))
    c.validate(level="index")
    c.validate(level="records")
    c.validate(level="full")
```

Use `docs/CONTAINER_FORMAT.md` for the normative container layout.
