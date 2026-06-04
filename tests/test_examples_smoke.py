"""Smoke tests for README-linked repository examples."""
import runpy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def run_script(path, *argv):
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

def test_container_query_example_runs(capsys):
    run_script("examples/container_query.py")
    assert "Record hashes differ: True" in capsys.readouterr().out

def test_conversion_example_runs(capsys):
    run_script("examples/conversion_with_pymatgen.py")
    assert "pymatgen formula:" in capsys.readouterr().out

def test_properties_and_hashes_example_runs(capsys):
    run_script("examples/properties_and_hashes.py")
    assert "Record hash:" in capsys.readouterr().out

def test_download_mp_data_help_runs_without_api_key(capsys):
    run_script("examples/download_mp_data.py", "--help")
    assert "Materials Project" in capsys.readouterr().out
