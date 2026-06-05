# Validate and Recover Containers

```python
result = container.validate(level="index")
if not result.ok:
    print(result.errors)

rebuilt = container.rebuild_index()
```

Use `level="full"` when you need full record decoding and record-hash verification.
