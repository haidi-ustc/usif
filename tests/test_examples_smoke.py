"""Smoke tests for repository examples."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_example(*args):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_example_1_runs():
    run_example("examples/example-1.py")


def test_example_2_runs():
    run_example("examples/example-2.py")


def test_download_mp_data_help_runs_without_api_key():
    result = run_example("examples/download_mp_data.py", "--help")
    assert "Materials Project" in result.stdout
