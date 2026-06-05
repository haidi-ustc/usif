"""Release-version metadata tests."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def test_pyproject_is_single_release_metadata_source():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    project = pyproject["project"]
    release = pyproject["tool"]["usif"]["release"]

    assert project["version"] == "6.0.0"
    assert "dynamic" not in project
    assert release == {
        "date": "2026-06-05",
        "sequence": 1,
        "record": "20260605.001",
        "id": "usif-20260605-001",
    }


def test_usif_version_metadata_matches_pyproject():
    import usif

    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    release = pyproject["tool"]["usif"]["release"]

    assert usif.__version__ == pyproject["project"]["version"]
    assert usif.RELEASE_DATE == release["date"]
    assert usif.RELEASE_RECORD == release["record"]
    assert usif.RELEASE_ID == release["id"]
