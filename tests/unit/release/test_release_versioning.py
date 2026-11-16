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

    assert project["version"] == "0.10.0"
    assert "dynamic" not in project
    assert release == {
        "date": "2026-11-16",
        "sequence": 19,
        "record": "20261116.019",
        "id": "usif-20261116-019",
    }


def test_usif_version_metadata_matches_pyproject():
    import usif
    from usif import version

    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    release = pyproject["tool"]["usif"]["release"]

    assert usif.__version__ == pyproject["project"]["version"]
    assert version.RELEASE_DATE == release["date"]
    assert version.RELEASE_RECORD == release["record"]
    assert version.RELEASE_ID == release["id"]


def test_release_metadata_checker_passes_and_can_write_report(tmp_path):
    from scripts.check_release_metadata import main, validate_release_metadata

    meta = validate_release_metadata(Path.cwd())
    assert meta.version == "0.10.0"
    assert meta.record == "20261116.019"

    report = tmp_path / "release-checks.txt"
    assert main(["--root", str(Path.cwd()), "--write-report", str(report)]) == 0
    text = report.read_text()
    assert "USIF release metadata check: PASS" in text
    assert "record=20261116.019" in text


def test_release_constants_are_public():
    """The CI and publish wheel smoke steps assert these on the installed package."""
    import usif

    assert usif.RELEASE_RECORD == "20261116.019"
    assert usif.RELEASE_ID == "usif-20261116-019"
    assert {"RELEASE_RECORD", "RELEASE_ID", "RELEASE_DATE"} <= set(usif.__all__)
