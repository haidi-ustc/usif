# USIF Binary Round-trip

```python
from usif import USIF

codec = USIF()
data = codec.encode(structure)
loaded, geometry_hash = codec.decode(data)
print(loaded.formula, geometry_hash.hex())
```

See `examples/01_manual_structure_binary_roundtrip.py`.
