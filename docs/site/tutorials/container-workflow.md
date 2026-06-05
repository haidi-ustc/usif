# Container Workflow

```python
from usif.storage import StructureContainer

with StructureContainer("materials.usifc", mode="w") as c:
    c.add(structure, name="sample", group="/examples")

with StructureContainer("materials.usifc", mode="r") as c:
    print(c.stats())
    print(c.query(has_property="energy"))
    print(c.validate(level="full").ok)
```

See `examples/02_container_write_query_validate.py` and `examples/09_large_container_workflow.py`.
