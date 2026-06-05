# Materials Project Dataset

Materials Project support is optional and lives under `usif.integrations.materials_project`.

```python
from usif.integrations.materials_project import load_mp_group, convert_mp_to_usif

docs = load_mp_group("mp_dataset/group_01/materials.json")
structure = convert_mp_to_usif(docs[0])
```

Live downloads require the `mp` extra and an API key. See `examples/download_mp_data.py` and `examples/README_MP_DOWNLOAD.md`.
