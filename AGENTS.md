# Repository Guidelines

## Project Structure & Module Organization

USIF is a Python package for crystal and molecular structure interchange. Core source code lives in `usif/`: `structures/` defines structure and site models, `properties/` contains property definitions and serialization, and top-level modules such as `encoder.py`, `converter.py`, `container.py`, and `units.py` provide format, conversion, and utility behavior. Tests are in `tests/` with shared setup in `tests/conftest.py`; test data belongs under `tests/data/`. Examples and Materials Project helpers are in `examples/`, while design notes and module documentation are in `docs/`.

## Build, Test, and Development Commands

- `pip install -e ".[all]"`: install the package in editable mode with test and lint dependencies.
- `python -m pytest`: run the pytest suite configured by `pyproject.toml`.
- `python run_tests.py`: run the repository's unittest discovery wrapper.
- `python run_lint.py`: run `isort --check-only --diff` and `flake8` over `usif`, `tests`, and `examples`.
- `isort usif tests examples`: fix import ordering before re-running lint checks.

## Coding Style & Naming Conventions

Use Python 3.8+ compatible code. Follow the existing 4-space indentation style and keep public APIs explicit and readable. Modules and functions use `snake_case`, classes use `PascalCase`, and constants use `UPPER_SNAKE_CASE`. Keep imports sorted with isort's `black` profile and 100-character line length. Prefer established package patterns, especially dataclass-like structure models, enum/constants definitions, and property registry helpers.

## Testing Guidelines

Add or update tests for behavioral changes, serialization changes, and conversion edge cases. Test files must match `tests/test_*.py`; test classes should start with `Test`, and test functions with `test_`. Keep fixtures and path setup in `tests/conftest.py` rather than modifying `sys.path` in individual tests. Place reusable binary or archive fixtures in `tests/data/`.

## Commit & Pull Request Guidelines

Recent commits use concise imperative summaries, for example `Fix incorrect use of COORDINATE_TOLERANCE for non-coordinate variables` or `Update as_dict to save structure-type-specific properties only`. Use that style: state the changed behavior, not the process. Pull requests should include a short description, linked issue when applicable, the tests or lint commands run, and notes for format, serialization, or API compatibility changes. Include screenshots only for documentation or example-output changes where visual review is useful.

## Security & Configuration Tips

Do not commit generated build outputs, virtual environments, coverage reports, or downloaded Materials Project data beyond intentional fixtures. Keep credentials and API keys out of the repository; pass them through environment variables or local configuration files ignored by git.
