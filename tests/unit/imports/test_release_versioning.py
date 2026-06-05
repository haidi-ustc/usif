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

    assert project["version"] == "6.7.0"
    assert "dynamic" not in project
    assert release == {
        "date": "2026-06-05",
        "sequence": 12,
        "record": "20260605.012",
        "id": "usif-20260605-012",
    }


def test_usif_version_metadata_matches_pyproject():
    import usif

    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    release = pyproject["tool"]["usif"]["release"]

    assert usif.__version__ == pyproject["project"]["version"]
    assert usif.RELEASE_DATE == release["date"]
    assert usif.RELEASE_RECORD == release["record"]
    assert usif.RELEASE_ID == release["id"]


def test_release_metadata_checker_passes_and_can_write_report(tmp_path):
    from scripts.check_release_metadata import validate_release_metadata, main

    meta = validate_release_metadata(Path.cwd())
    assert meta.version == "6.7.0"
    assert meta.record == "20260605.012"

    report = tmp_path / "release-checks.txt"
    assert main(["--root", str(Path.cwd()), "--write-report", str(report)]) == 0
    text = report.read_text()
    assert "USIF release metadata check: PASS" in text
    assert "record=20260605.012" in text
