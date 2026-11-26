"""Every example script runs and prints what its README entry promises."""

import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"

EXPECTED = {
    "quickstart.py": ["Formula: NaCl", "Round trip exact: True", "['/salts/nacl']"],
    "01_structures_and_records.py": [
        "symmetric=True",
        "Same geometry hash: True",
        "Exact decode: True",
        "JSON exact: True",
    ],
    "02_dataset_workflow.py": ["Entries: 12, records: 11", "Validation ok: True"],
    "03_library_conversion.py": [],
    "04_upgrade_0_8_files.py": ["Imported 6 entries", "Validation ok: True"],
    "05_cli_workflow.py": ["$ usif validate"],
    "06_local_dataset.py": [
        "Found 3 structures, 3 new",
        "Applied: 3 added",
        "New after import: 0",
        "Near the minimum: ['/salts/eos/a5.60/final']",
        "Added by plan: 3",
    ],
    "07_agent_projects.py": [
        "link      /projects/stable/SrTiO3/relax  <-  /oer/SrTiO3/relax",
        "Applied: 1 project, 2 links",
        "Search tool found: ['/projects/stable/SrTiO3/relax', '/projects/stable/BaTiO3/relax']",
        "Proposed by the question: 0 changes",
        "Records stored: 3 (links copy nothing)",
        "Projects: [('stable', 2)]",
    ],
}


def test_every_example_is_listed():
    scripts = {p.name for p in EXAMPLES.glob("*.py")}
    assert scripts == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_runs(name, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(EXAMPLES / name)])
    try:
        runpy.run_path(str(EXAMPLES / name), run_name="__main__")
    except SystemExit as exc:
        assert exc.code in (0, None)
    out = capsys.readouterr().out
    for text in EXPECTED[name]:
        assert text in out, f"{name} did not print {text!r}"
    if name == "03_library_conversion.py":
        assert "exact round trip: False" not in out


def test_benchmark_script(capsys):
    from scripts.benchmark import benchmark, synthetic_structures

    results = benchmark(synthetic_structures(count=2, natoms=50))
    assert {"json", "none", "zlib", "zlib+f32"} <= set(results)
    assert results["zlib+f32"]["bytes_per_atom"] < results["json"]["bytes_per_atom"]
