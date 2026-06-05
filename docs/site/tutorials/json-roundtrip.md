# JSON Round-trip

```python
from usif.services import save_structure, load_structure, structure_to_json_dict

save_structure(structure, "sample.usif.json")
loaded = load_structure("sample.usif.json")
print(structure_to_json_dict(loaded)["@schema"])
```

See `examples/06_json_structure_roundtrip.py`.
