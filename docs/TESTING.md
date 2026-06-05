# Testing USIF

USIF uses a layered pytest suite so contributors can run the right amount of validation for the change they are making.

## Test layers

| Layer | Path | Purpose |
|---|---|---|
| Unit | `tests/unit/` | Fast model, property, codec, storage, and import-boundary checks. |
| Integration | `tests/integration/` | pymatgen/ASE adapters, service orchestration, and Materials Project fixture integration. |
| Reliability | `tests/reliability/` | Corruption handling, integrity checks, recovery behavior, and concurrency checks. |
| Examples | `tests/examples/` | Smoke tests for the runnable repository examples. |
| Fixtures | `tests/fixtures/` | Bundled deterministic test data. No tests live here. |

## Common commands

```bash
python -m pytest tests/unit
python -m pytest tests/integration tests/reliability tests/examples
python -m pytest -m "not slow and not network"
python -m pytest --cov=usif --cov-report=term-missing
```

Network-dependent Materials Project downloads are not part of the default suite. Tests under `tests/integration/materials_project` use the bundled fixture archive unless `MP_DATA_DIR` points at another local dataset.

## Markers

Markers are registered in `pyproject.toml` and applied automatically by `tests/conftest.py` from the directory layout:

- `unit`
- `integration`
- `interop`
- `mp_data`
- `network`
- `slow`
- `reliability`
- `examples`

Use explicit markers only when a single test needs a narrower meaning than its directory.
