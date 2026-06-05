"""Engineering workflow and release-layout guardrails."""

from __future__ import annotations

from pathlib import Path


TEST_LAYERS = {
    "unit",
    "integration",
    "reliability",
    "examples",
    "fixtures",
}


REQUIRED_MARKERS = {
    "unit",
    "integration",
    "interop",
    "mp_data",
    "network",
    "slow",
    "reliability",
    "examples",
}


def test_test_suite_uses_layered_directory_layout():
    root = Path("tests")
    assert TEST_LAYERS.issubset({path.name for path in root.iterdir() if path.is_dir()})
    assert not list(root.glob("test_*.py"))
    assert (root / "conftest.py").exists()


def test_pytest_markers_are_registered_in_pyproject():
    text = Path("pyproject.toml").read_text()
    for marker in REQUIRED_MARKERS:
        assert f'"{marker}:' in text
    assert 'testpaths = ["tests/unit", "tests/integration", "tests/reliability", "tests/examples"]' in text


def test_ci_workflow_covers_quality_test_and_build_smoke():
    workflow = Path(".github/workflows/ci.yml")
    assert workflow.exists()
    text = workflow.read_text()
    for expected in (
        "black --check",
        "isort --check-only",
        "mypy usif",
        "bandit -q -r usif",
        "pip_audit",
        "pytest tests/unit",
        "pytest tests/integration tests/reliability tests/examples",
        "python -m build",
        "dist/*.whl",
    ):
        assert expected in text


def test_release_artifact_hygiene_files_are_configured():
    assert not Path("setup.cfg").exists()
    manifest = Path("MANIFEST.in").read_text()
    for excluded in ("docs/archive", ".pytest_cache", "build", "dist", "*.egg-info"):
        assert excluded in manifest
    assert "docs/RELEASE.md" in manifest
    assert "docs/TESTING.md" in manifest
