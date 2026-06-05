# Contributing

Install development dependencies with `python -m pip install -e ".[dev,ase]"`. Before opening a PR, run:

```bash
python -m black --check usif tests examples
python -m isort --check-only usif tests examples
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest
python -m pytest --cov=usif --cov-report=term-missing --cov-fail-under=70
python -m mypy usif/format usif/storage usif/properties
python -m bandit -q -r usif -x tests
```

README-linked examples must have smoke coverage in `tests/test_examples_smoke.py`. Prefer `MP_API_KEY` over command-line API keys.
