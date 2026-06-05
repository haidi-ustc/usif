"""Shared pytest configuration for the layered USIF test suite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MP_DATA_DIR = REPO_ROOT / "tests" / "fixtures" / "mp_structures"


def pytest_configure(config: pytest.Config) -> None:
    """Register markers used by CI and local test selection."""
    config.addinivalue_line("markers", "unit: fast tests with no optional external services")
    config.addinivalue_line("markers", "integration: adapter/service tests that may need optional packages")
    config.addinivalue_line("markers", "interop: pymatgen or ASE interoperability tests")
    config.addinivalue_line("markers", "mp_data: tests that exercise bundled Materials Project fixture data")
    config.addinivalue_line("markers", "network: tests that require live external network/API access")
    config.addinivalue_line("markers", "slow: long-running tests or larger fixture sweeps")
    config.addinivalue_line("markers", "reliability: corruption, integrity, recovery, and concurrency tests")
    config.addinivalue_line("markers", "examples: repository example smoke tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply broad markers from the tests/ directory layout."""
    for item in items:
        path = Path(str(item.fspath)).resolve()
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) < 2 or parts[0] != "tests":
            continue
        layer = parts[1]
        if layer == "unit":
            item.add_marker(pytest.mark.unit)
        elif layer == "integration":
            item.add_marker(pytest.mark.integration)
            if "interop" in parts:
                item.add_marker(pytest.mark.interop)
            if "materials_project" in parts:
                item.add_marker(pytest.mark.mp_data)
        elif layer == "reliability":
            item.add_marker(pytest.mark.reliability)
        elif layer == "examples":
            item.add_marker(pytest.mark.examples)


@pytest.fixture(autouse=True, scope="session")
def _default_mp_fixture_path() -> None:
    """Point MP-data tests at the repository fixture archive unless callers override it."""
    os.environ.setdefault("MP_DATA_DIR", str(DEFAULT_MP_DATA_DIR))
