# Release Process

This project uses `pyproject.toml` as the single packaging configuration and release metadata source. See `docs/VERSIONING.md` for the date-based unique release record scheme. `setup.cfg` and generated egg-info directories are intentionally not part of the source tree.

## Pre-release checklist

1. Update `[project].version` and `[tool.usif.release]` in `pyproject.toml`.
2. Update `docs/CHANGELOG.md`.
3. Validate release metadata:

```bash
python scripts/check_release_metadata.py --write-report release-checks.txt
```

4. Run formatting, type, security, and dependency checks:

```bash
python -m black --check usif tests examples
python -m isort --check-only usif tests examples
python -m mypy usif
python -m bandit -q -r usif -x tests
python -m pip_audit
```

5. Run the layered tests:

```bash
python -m pytest tests/unit --cov=usif --cov-report=term-missing
python -m pytest tests/integration tests/reliability tests/examples
```

6. Build artifacts:

```bash
python -m build
```

7. Install and smoke-test the built wheel in a clean virtual environment:

```bash
python -m venv /tmp/usif-wheel-smoke
/tmp/usif-wheel-smoke/bin/python -m pip install dist/*.whl
/tmp/usif-wheel-smoke/bin/python - <<'PY'
import usif
assert usif.__version__ == "7.0.0"
assert usif.RELEASE_RECORD == "20260605.015"
from usif import USIF, USIFStructure
from usif.storage import StructureContainer
print("USIF wheel smoke OK", usif.__version__)
PY
```

## Artifact hygiene

Source archives should not contain local caches, generated build outputs, or historical planning archives unless intentionally requested. Keep the published package focused on runtime code, tests, current docs, examples, and deterministic fixtures.
