"""``usif dataset import`` and ``usif agent ...``: scanning real calculation layouts, approval."""

import json
import os
import sys

import numpy as np
import pytest

from usif import Cell, Structure, io
from usif.cli import main
from usif.dataset import Dataset


def run(capsys, *argv):
    code = main(list(map(str, argv)))
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.fixture(autouse=True)
def no_user_config(tmp_path, monkeypatch):
    monkeypatch.setenv("USIF_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def vasp_project(tmp_path):
    ase_io = pytest.importorskip("ase.io")
    from ase import Atoms
    from ase.calculators.singlepoint import SinglePointCalculator

    root = tmp_path / "project"
    for system, a, energy in (("SrTiO3", 3.905, -40.1), ("BaTiO3", 4.0, -41.2)):
        calc = root / "perovskites" / system / "relax"
        calc.mkdir(parents=True)
        atoms = Atoms(
            system,
            scaled_positions=[[0, 0, 0], [0.5] * 3, [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]],
            cell=[a] * 3,
            pbc=True,
        )
        ase_io.write(calc / "POSCAR", atoms, format="vasp")
        (calc / "INCAR").write_text("ENCUT = 520\nISPIN = 2 ; LDAU = .TRUE.\n")
        (calc / "KPOINTS").write_text("auto\n0\nGamma\n8 8 8\n")
        atoms.calc = SinglePointCalculator(
            atoms, energy=energy, forces=np.zeros((5, 3)), stress=np.zeros(6)
        )
        ase_io.write(calc / "final.extxyz", atoms, format="extxyz")
    (root / "perovskites" / "README.md").write_text("Perovskite oxides for OER, PBE+U.")
    return root


def test_import_scans_vasp_directories_and_needs_approval(capsys, vasp_project, tmp_path):
    target = tmp_path / "group.usifc"
    code, out, _ = run(capsys, "dataset", "import", vasp_project, target, "--group", "/oer")
    assert code == 0 and "4 new" in out and "not applied" in out and not target.exists()
    plan_file = next((tmp_path / "home" / "plans").glob("*.json"))
    code, out, _ = run(capsys, "agent", "show", plan_file)
    assert code == 0 and "add       /oer/perovskites/SrTiO3/relax" in out
    assert run(capsys, "agent", "apply", plan_file)[0] == 2  # not a terminal and no --yes
    code, out, _ = run(capsys, "agent", "plans")
    assert code == 0 and "1 plans" in out and "4 ops" in out
    code, out, _ = run(capsys, "agent", "apply", plan_file, "--yes")
    assert code == 0 and "4 add" in out
    assert not plan_file.exists()  # moved to the journal of applied plans
    code, out, _ = run(capsys, "agent", "plans", "--applied", "--json")
    assert [row["operations"] for row in json.loads(out)] == [4]
    with Dataset(target, "r") as data:
        entry = data.entry("/oer/perovskites/SrTiO3/relax")
        assert entry.attrs["code"] == "vasp" and entry.attrs["incar"]["ENCUT"] == 520
        assert entry.attrs["notes"].startswith("Perovskite oxides")
        final = data["/oer/perovskites/BaTiO3/relax/final"]
        assert final.properties["energy"] == pytest.approx(-41.2)
    code, out, _ = run(capsys, "dataset", "import", vasp_project, target, "--group", "/oer", "-y")
    assert code == 0 and "4 already registered" in out and "nothing to change" in out


def test_import_with_yes_and_saved_plan(capsys, tmp_path):
    source = tmp_path / "runs"
    source.mkdir()
    io.write(
        Structure.from_fractional([11, 17], [[0, 0, 0], [0.5] * 3], Cell.cubic(5.6)),
        source / "nacl.usif",
    )
    plan_path = tmp_path / "plan.json"
    code, out, _ = run(
        capsys, "dataset", "import", source, "d.usifc", "--plan-out", plan_path, "--yes"
    )
    assert code == 0 and "applied plan" in out and plan_path.exists()
    assert json.loads(plan_path.read_text())["format"] == "usif.agent.plan.v1"


def test_agent_config_never_prints_the_key(capsys, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret-value")
    code, out, _ = run(capsys, "agent", "config", "--json")
    data = json.loads(out)
    assert code == 0 and data["api_key_set"] is True and "sk-secret-value" not in out
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    code, _, err = run(capsys, "agent", "ask", "d.usifc", "hello")
    assert code == 2 and "usif: error: set DEEPSEEK_API_KEY" in err


def test_agent_ask_with_a_scripted_model(capsys, monkeypatch, tmp_path):
    import usif.agent as agent

    with Dataset(tmp_path / "d.usifc") as data:
        data.add(
            Structure.from_fractional([11, 17], [[0, 0, 0], [0.5] * 3], Cell.cubic(5.6)),
            "nacl",
            "/s",
        )

    replies = [
        {
            "tool_calls": [
                {
                    "id": "1",
                    "function": {
                        "name": "propose_remove",
                        "arguments": json.dumps({"path": "/s/nacl", "reason": "test"}),
                    },
                }
            ]
        },
        {"content": "I proposed removing /s/nacl."},
    ]

    class Fake:
        def __init__(self, config):
            self.config = config

        def complete(self, messages, tools):
            return replies.pop(0)

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    monkeypatch.setattr(agent, "ChatClient", Fake)
    code, out, err = run(capsys, "agent", "ask", "d.usifc", "remove nacl", "--plan-out", "p.json")
    assert code == 0 and "I proposed removing" in out and "remove    /s/nacl" in out
    assert "[propose_remove]" in err and "not applied" in out
    with Dataset(tmp_path / "d.usifc", "r") as data:
        assert "/s/nacl" in data  # nothing happens without approval


def test_agent_creates_a_project_only_after_approval(capsys, monkeypatch, tmp_path):
    import usif.agent as agent

    arguments = {"name": "oer", "description": "OER perovskites", "reason": "asked"}
    replies = [
        {
            "tool_calls": [
                {
                    "id": "1",
                    "function": {"name": "propose_project", "arguments": json.dumps(arguments)},
                }
            ]
        },
        {"content": "I proposed the project /projects/oer."},
    ]

    class Fake:
        def __init__(self, config):
            self.config = config

        def complete(self, messages, tools):
            return replies.pop(0)

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    monkeypatch.setattr(agent, "ChatClient", Fake)
    target = tmp_path / "new.usifc"
    code, out, _ = run(
        capsys, "agent", "ask", target, "start a project for OER", "--plan-out", "p.json"
    )
    assert code == 0 and "group     /projects/oer" in out and "not applied" in out
    assert not target.exists()  # the dataset is created only by the approved plan
    code, out, _ = run(capsys, "agent", "apply", "p.json", "--yes")
    assert code == 0 and "1 set_group_attrs" in out
    with Dataset(target, "r") as data:
        assert data.group_attrs("/projects/oer") == {"description": "OER perovskites"}


@pytest.mark.parametrize(
    "argv", [["agent"], ["agent", "-h"], ["agent", "ask", "-h"], ["dataset", "import", "-h"]]
)
def test_agent_help(capsys, argv):
    code, out, _ = run(capsys, *argv)
    assert code == 0 and "Usage: usif" in out


@pytest.mark.network
@pytest.mark.skipif(not os.environ.get("DEEPSEEK_API_KEY"), reason="DEEPSEEK_API_KEY not set")
def test_live_deepseek_answers_from_the_dataset(tmp_path, monkeypatch):
    """A real request: the model must call a tool and report the stored energy."""
    from usif.agent import ChatClient, Session, Toolbox, load_config

    path = tmp_path / "live.usifc"
    with Dataset(path) as data:
        data.add(
            Structure.from_fractional(
                [11, 17], [[0, 0, 0], [0.5] * 3], Cell.cubic(5.64), properties={"energy": -27.123}
            ),
            "nacl",
            "/salts",
        )
    used = []
    session = Session(
        ChatClient(load_config()), Toolbox(path), on_tool=lambda name, args: used.append(name)
    )
    answer = session.ask("What is the energy of the NaCl entry? Reply with the number only.")
    assert used and "-27.123" in answer.replace("−", "-")
    key = os.environ["DEEPSEEK_API_KEY"]
    assert all(key not in json.dumps(m) for m in session.messages)


def test_model_answers_cannot_inject_terminal_escapes():
    from usif.cli.agent import terminal_text

    assert terminal_text("a\x1b[2Jb\nc\td") == "a\\x1b[2Jb\nc\td"
