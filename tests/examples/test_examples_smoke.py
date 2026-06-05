"""Smoke tests for README-linked repository examples."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not locate repository root")


ROOT = _repo_root()


def run_script(path: str, *argv: str) -> None:
    old_argv = sys.argv[:]
    sys.argv = [str(ROOT / path), *argv]
    try:
        try:
            runpy.run_path(str(ROOT / path), run_name="__main__")
        except SystemExit as exc:
            assert exc.code in (0, None)
    finally:
        sys.argv = old_argv


def test_quickstart_example_runs(capsys):
    run_script("examples/quickstart.py")
    assert "Formula: NaCl" in capsys.readouterr().out


def test_manual_binary_roundtrip_example_runs(capsys):
    run_script("examples/01_manual_structure_binary_roundtrip.py")
    out = capsys.readouterr().out
    assert "Manual formula: NaCl" in out
    assert "Record hash:" in out


def test_container_write_query_validate_example_runs(capsys):
    run_script("examples/02_container_write_query_validate.py")
    out = capsys.readouterr().out
    assert "Record hashes differ: True" in out
    assert "Validation ok: True" in out


def test_pymatgen_conversion_roundtrip_example_runs(capsys):
    run_script("examples/03_pymatgen_conversion_roundtrip.py")
    assert "pymatgen formula:" in capsys.readouterr().out


def test_properties_and_hashes_example_runs(capsys):
    run_script("examples/04_properties_and_hashes.py")
    assert "Record hash:" in capsys.readouterr().out


def test_symmetry_policy_import_example_runs(capsys):
    run_script("examples/05_symmetry_policy_import.py")
    out = capsys.readouterr().out
    assert "Analyze policy mode:" in out
    assert "None policy mode:" in out




def test_json_structure_roundtrip_example_runs(capsys):
    run_script("examples/06_json_structure_roundtrip.py")
    out = capsys.readouterr().out
    assert "JSON schema: usif.structure.json.v1" in out
    assert "JSON formula: C2" in out


def test_download_mp_data_help_runs_without_api_key(capsys):
    run_script("examples/download_mp_data.py", "--help")
    assert "Materials Project" in capsys.readouterr().out


def test_property_units_example_runs(capsys):
    run_script("examples/08_property_units.py")
    out = capsys.readouterr().out
    assert "Angstrom alias: Å^2" in out
    assert "Force units: eV/Å" in out


def test_large_container_workflow_example_runs(capsys):
    run_script("examples/09_large_container_workflow.py")
    out = capsys.readouterr().out
    assert "Indexed records: 3" in out
    assert "Indexed properties include metadata.family: True" in out
    assert "Hydride query count: 2" in out


def test_materials_project_dataset_example_help_runs(capsys):
    run_script("examples/10_materials_project_dataset.py", "--help")
    assert "Materials Project" in capsys.readouterr().out
