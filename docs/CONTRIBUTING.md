# Contributing

Install development dependencies with `python -m pip install -e ".[dev,ase,mp]"`. Before opening a PR, run the same layered checks used by CI:

```bash
python -m black --check usif tests examples
python -m isort --check-only usif tests examples
python -m mypy usif
python -m bandit -q -r usif -x tests
python -m pip_audit
python -m pytest tests/unit --cov=usif --cov-report=term-missing
python -m pytest tests/integration tests/reliability tests/examples
```

README-linked examples must have smoke coverage under `tests/examples/`. Materials Project tests should use deterministic fixtures under `tests/fixtures/`; live API/network checks must be explicitly marked `network` and skipped by default. Prefer `MP_API_KEY` over command-line API keys. See `docs/TESTING.md` and `docs/RELEASE.md` for the full workflow.
