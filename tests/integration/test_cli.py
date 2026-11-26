"""The ``usif`` command line, driven through :func:`usif.cli.main`."""

import json
import re
import shutil
from pathlib import Path

import pytest

from usif import Cell, Structure, io
from usif.cli import main

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# Rich styles the help panels when the environment forces colour (CI exports
# FORCE_COLOR), which splits "Usage: usif" across escape sequences; assertions
# read the stripped text.
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def run(capsys, *argv):
    code = main(list(map(str, argv)))
    out = capsys.readouterr()
    return code, ANSI.sub("", out.out), ANSI.sub("", out.err)


@pytest.fixture
def nacl_file(tmp_path):
    path = tmp_path / "nacl.usif"
    structure = Structure.from_fractional(
        [11, 17], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(3.0), properties={"energy": -2.0}
    )
    io.write(structure, path)
    return path


def test_version(capsys):
    code, out, _ = run(capsys, "version", "--json")
    data = json.loads(out)
    assert code == 0 and data["format_version"] == 7 and data["dataset_schema"] == 1
    assert run(capsys, "--version")[1].startswith("USIF ")


def test_inspect_convert_validate(capsys, nacl_file, tmp_path):
    code, out, _ = run(capsys, "inspect", nacl_file, "--json")
    summary = json.loads(out)
    assert code == 0 and summary["reduced_formula"] == "NaCl" and summary["record"]["format"] == 7
    json_path = tmp_path / "nacl.json"
    assert run(capsys, "convert", nacl_file, json_path)[0] == 0
    out_path = tmp_path / "again.usif"
    code, _, _ = run(
        capsys, "convert", json_path, out_path, "--precision", "f32", "--compression", "lzma"
    )
    assert code == 0 and io.read(out_path).allclose(io.read(nacl_file), atol=1e-6)
    assert run(capsys, "validate", out_path)[0] == 0
    bad = tmp_path / "bad.usif"
    bad.write_bytes(out_path.read_bytes()[:-3])
    code, out, _ = run(capsys, "validate", bad, "--json")
    assert code == 1 and json.loads(out)["ok"] is False


def test_upgrade_record_and_container(capsys, tmp_path):
    record = tmp_path / "new.usif"
    assert run(capsys, "upgrade", FIXTURES / "format5" / "rutile_136.usif", record)[0] == 0
    assert io.read(record).reduced_formula == "TiO2"
    dataset = tmp_path / "data.usifc"
    code, out, _ = run(capsys, "upgrade", FIXTURES / "format5" / "mixed.usifc", dataset)
    assert code == 0 and "4 entries" in out
    code, out, _ = run(capsys, "inspect", dataset, "--json")
    assert json.loads(out)["entries"] == 4
    old = tmp_path / "old.usifc"
    shutil.copy(FIXTURES / "format5" / "mixed.usifc", old)
    assert "usif upgrade" in run(capsys, "inspect", old)[1]
    assert run(capsys, "validate", dataset, "--full")[0] == 0


def test_dataset_commands(capsys, nacl_file, tmp_path):
    dataset = tmp_path / "data.usifc"
    water = tmp_path / "water.json"
    io.write(Structure([8, 1, 1], [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]]), water)
    code, out, _ = run(capsys, "dataset", "add", dataset, nacl_file, water, "--group", "/set")
    assert code == 0 and "added 2" in out
    code, out, _ = run(capsys, "dataset", "list", dataset, "--formula", "NaCl", "--json")
    rows = json.loads(out)
    assert [r["path"] for r in rows] == ["/set/nacl"] and rows[0]["attrs"] == {
        "source": "nacl.usif"
    }
    code, out, _ = run(
        capsys, "dataset", "list", dataset, "--prop", "energy<-1", "--elements", "Na"
    )
    assert code == 0 and "1 entries" in out
    code, _, err = run(capsys, "dataset", "list", dataset, "--prop", "energy<<1")
    assert code == 2 and "needs a number" in err
    exported = tmp_path / "out.usif"
    assert run(capsys, "dataset", "export", dataset, exported, "--entry", "/set/water")[0] == 0
    assert io.read(exported).reduced_formula == "H2O"
    assert run(capsys, "dataset", "compact", dataset)[0] == 0


@pytest.fixture
def salts(tmp_path):
    from usif.dataset import Dataset

    path = tmp_path / "salts.usifc"
    with Dataset(path, "w") as dataset:
        for group, numbers, energy in (
            ("/salts", [11, 17], -1.0),
            ("/salts", [19, 17], -2.0),
            ("/other", [11, 35], -3.0),
        ):
            structure = Structure.from_fractional(
                numbers,
                [[0, 0, 0], [0.5, 0.5, 0.5]],
                Cell.cubic(3.0),
                properties={"energy": energy},
            )
            dataset.add(structure, structure.reduced_formula, group)
    return path


def test_export_selected_entries_to_one_file(capsys, tmp_path, salts):
    pytest.importorskip("ase")
    out = tmp_path / "salts.extxyz"
    code, text, _ = run(capsys, "dataset", "export", salts, out, "--group", "/salts")
    assert code == 0 and "2 structures" in text
    assert [s.reduced_formula for s in io.read_all(out)] == ["NaCl", "KCl"]  # dataset order
    code, _, err = run(capsys, "dataset", "export", salts, out)
    assert code == 2 and "--overwrite" in err and len(io.read_all(out)) == 2  # refused
    code, text, _ = run(capsys, "dataset", "export", salts, out, "--overwrite", "--limit", "3")
    assert code == 0 and len(io.read_all(out)) == 3
    code, _, _ = run(
        capsys, "dataset", "export", salts, out, "--overwrite", "--prop", "energy<-1.5"
    )
    assert code == 0 and [s.reduced_formula for s in io.read_all(out)] == ["KCl", "NaBr"]
    entries = ("--entry", "/other/NaBr", "--entry", "/salts/NaCl")
    code, _, _ = run(capsys, "dataset", "export", salts, out, "--overwrite", *entries)
    assert code == 0 and [s.reduced_formula for s in io.read_all(out)] == ["NaBr", "NaCl"]
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []  # no scratch


def test_export_refusals_write_nothing(capsys, tmp_path, salts):
    one = tmp_path / "one.usif"
    code, text, _ = run(capsys, "dataset", "export", salts, one, "--formula", "KCl")
    assert code == 0 and "1 structure ->" in text and io.read(one).reduced_formula == "KCl"
    before = one.read_bytes()
    for argv, message in (
        ((one, "--formula", "NaBr"), "--overwrite"),
        ((tmp_path / "many.usif", "--group", "/salts"), "multi-frame"),
        ((tmp_path / "none.xyz", "--formula", "XeF2"), "no entries match"),
        ((tmp_path / "e.json", "--entry", "/salts/KCl", "--group", "/salts"), "filters"),
        ((tmp_path / "missing.json", "--entry", "/salts/LiF"), "not found"),
        ((tmp_path / "copy.usifc",), "not a .usifc"),
    ):
        code, _, err = run(capsys, "dataset", "export", salts, *argv)
        assert code == 2 and message in err and err.startswith("usif: error:")
    assert run(capsys, "dataset", "export", salts, tmp_path / "x.xyz", "--limit", "0")[0] == 2
    assert one.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["one.usif", "salts.usifc"]
    code, _, _ = run(capsys, "dataset", "export", salts, one, "--formula", "NaBr", "--overwrite")
    assert code == 0 and io.read(one).reduced_formula == "NaBr"


def test_errors_and_usage(capsys, tmp_path):
    code, _, err = run(capsys, "inspect", tmp_path / "missing.usif")
    assert code == 2 and "usif: error" in err and "No such file or directory" in err
    assert run(capsys, "no-such-command")[0] == 2
    assert run(capsys, "dataset", "list")[0] == 2


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["-h"],
        ["--help"],
        ["dataset"],
        ["dataset", "-h"],
        ["dataset", "list", "-h"],
        ["inspect", "-h"],
        ["convert", "-h"],
        ["upgrade", "-h"],
        ["validate", "-h"],
    ],
    ids=lambda argv: " ".join(argv) or "bare",
)
def test_help_is_shown_with_exit_code_zero(capsys, argv):
    code, out, err = run(capsys, *argv)
    assert code == 0, err
    assert "Usage: usif" in out and "Traceback" not in out + err


def test_scripts_accept_short_help():
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    for module in ("scripts.benchmark", "scripts.materials_project"):
        result = subprocess.run(
            [sys.executable, "-m", module, "-h"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=root,  # `python -m scripts...` resolves against the repository root
        )
        assert result.returncode == 0 and "Usage" in result.stdout, result.stderr
