"""CLI contract tests for the stable USIF command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from usif import StorageMode, StructureProperties, StructureType, USIFStructure, WyckoffSite
from usif.cli import main
from usif.services import load_structure, save_structure
from usif.storage import StructureContainer


def _manual_structure(formula: str = "NaCl", energy: float = -10.5) -> USIFStructure:
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 5.64,
        spacegroup=225,
        wyckoff_sites=[
            WyckoffSite(atomic_number=11, multiplicity=4, coords=(0.0, 0.0, 0.0)),
            WyckoffSite(atomic_number=17, multiplicity=4, coords=(0.5, 0.5, 0.5)),
        ],
        structure_properties=StructureProperties(energy=energy),
        formula=formula,
    )


def test_pyproject_declares_usif_console_script():
    text = Path("pyproject.toml").read_text()
    assert "[project.scripts]" in text
    assert 'usif = "usif.cli:main"' in text


def test_cli_uses_typer():
    import typer

    import usif.cli as cli

    assert isinstance(cli.app, typer.Typer)
    assert isinstance(cli.container_app, typer.Typer)
    source = Path("usif/cli.py").read_text()
    assert "import argparse" not in source


def test_cli_version_json(capsys):
    assert main(["version", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == "7.0.0"
    assert payload["release_record"] == "20260605.015"
    assert payload["format_version"] == 5


def test_cli_convert_inspect_and_validate_structure(tmp_path, capsys):
    usif_path = tmp_path / "nacl.usif"
    json_path = tmp_path / "nacl.usif.json"
    save_structure(_manual_structure(), usif_path)

    assert main(["convert", str(usif_path), str(json_path), "--json"]) == 0
    converted = json.loads(capsys.readouterr().out)
    assert converted["ok"] is True
    assert load_structure(json_path).formula == "NaCl"

    assert main(["inspect", str(json_path), "--json"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["type"] == "structure"
    assert inspected["formula"] == "NaCl"

    assert main(["validate", str(json_path), "--json"]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["ok"] is True


def test_cli_container_stats_list_query_and_validate(tmp_path, capsys):
    path = tmp_path / "materials.usifc"
    with StructureContainer(path, mode="w") as container:
        container.add(
            _manual_structure("NaCl", -10.5),
            name="nacl-low",
            group="/halides",
            attributes={"source": "cli-test"},
        )
        container.add(_manual_structure("NaCl", -10.0), name="nacl-high", group="/halides")

    assert main(["container", "stats", str(path), "--json"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["records"] == 2
    assert "NaCl" in stats["formulas"]

    assert main(["container", "list", str(path), "names"]) == 0
    assert "nacl-low" in capsys.readouterr().out

    assert main(["container", "query", str(path), "--formula", "NaCl", "--json"]) == 0
    query = json.loads(capsys.readouterr().out)
    assert query["count"] == 2

    assert main(["validate", str(path), "--level", "index", "--json"]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["ok"] is True
    assert validation["type"] == "container"
