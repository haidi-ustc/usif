"""The data agent without a network: config, HTTP client, scanning, plans, tools, session."""

import io as stdio
import json
import urllib.request
from pathlib import Path

import pytest

from usif import Cell, Structure, io
from usif.agent import (
    Operation,
    Plan,
    Session,
    Toolbox,
    apply_plan,
    llm,
    load_config,
    plan_from_scan,
)
from usif.agent import scan as scan_directory
from usif.agent.config import LLMConfig
from usif.agent.discover import parse_incar
from usif.agent.llm import ChatClient
from usif.dataset import Dataset, Q
from usif.errors import AgentError

KEY = "sk-test-secret-0123456789"


def nacl(a=5.64, energy=-6.8):
    return Structure.from_fractional(
        ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(a), properties={"energy": energy}
    )


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    (root / "salts" / "scan").mkdir(parents=True)
    (root / "README.md").write_text("Rock-salt equation of state, PBE.\n")
    io.write(nacl(5.6, -6.7), root / "salts" / "scan" / "a560.usif")
    io.write(nacl(5.7, -6.75), root / "salts" / "scan" / "a570.json")
    (root / "salts" / "ignored.txt").write_text("not a structure")
    (root / ".hidden").mkdir()
    io.write(nacl(), root / ".hidden" / "x.usif")
    return root


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("USIF_HOME", str(tmp_path / "home"))
    for name in ("USIF_LLM_BASE_URL", "USIF_LLM_MODEL", "USIF_LLM_API_KEY_ENV", "USIF_DATASET"):
        monkeypatch.delenv(name, raising=False)


# -- configuration and HTTP -------------------------------------------------------------


def test_deepseek_is_the_default_and_settings_layer(tmp_path, monkeypatch):
    config = load_config()
    assert (
        config.base_url == "https://api.deepseek.com" and config.api_key_env == "DEEPSEEK_API_KEY"
    )
    path = tmp_path / "home" / "config.toml"
    path.parent.mkdir()
    path.write_text('[llm]\nbase_url = "http://localhost:8000/v1"\nmodel = "qwen"\n')
    monkeypatch.setenv("USIF_LLM_MODEL", "llama")
    config = load_config({"temperature": 0.3})
    assert (config.base_url, config.model, config.temperature) == (
        "http://localhost:8000/v1",
        "llama",
        0.3,
    )
    path.write_text('[llm]\napi_key = "sk-x"\n')
    with pytest.raises(AgentError, match="environment variable"):
        load_config()
    with pytest.raises(AgentError, match="http"):
        LLMConfig(base_url="file:///etc/passwd")
    with pytest.raises(AgentError, match="https unless the server is local"):
        LLMConfig(base_url="http://llm.example.org/v1")
    assert LLMConfig(base_url="http://127.0.0.1:11434/v1").base_url.startswith("http://")


def test_key_is_only_sent_in_the_header(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", KEY)
    config = load_config()
    assert KEY not in json.dumps(config.describe()) and config.describe()["api_key_set"]
    seen = {}

    class Response(stdio.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = request.data.decode()
        seen["url"] = request.full_url
        reply = {"choices": [{"message": {"role": "assistant", "content": "hi"}}], "usage": {}}
        return Response(json.dumps(reply).encode())

    monkeypatch.setattr(llm._OPENER, "open", fake_urlopen)
    client = ChatClient(config)
    assert client.complete([{"role": "user", "content": "hello"}])["content"] == "hi"
    assert seen["auth"] == f"Bearer {KEY}" and KEY not in seen["body"]
    assert seen["url"] == "https://api.deepseek.com/chat/completions"
    assert json.loads(seen["body"])["model"] == "deepseek-flash"


def test_http_errors_are_redacted(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", KEY)

    def failing(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 401, "no", {}, stdio.BytesIO(f"bad key {KEY}".encode())
        )

    monkeypatch.setattr(llm._OPENER, "open", failing)
    with pytest.raises(AgentError) as info:
        ChatClient(load_config(), retries=0).complete([{"role": "user", "content": "x"}])
    assert "401" in str(info.value) and KEY not in str(info.value)
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    with pytest.raises(AgentError, match="DEEPSEEK_API_KEY"):
        ChatClient(load_config()).complete([])


# -- scanning and plans ----------------------------------------------------------------------


def test_scan_finds_structures_with_provenance(project, tmp_path):
    result = scan_directory(project, group="/eos")
    paths = sorted(c.path for c in result.candidates)
    assert paths == ["/eos/salts/scan/a560", "/eos/salts/scan/a570"]
    first = result.candidates[0]
    assert first.attrs["notes"] == "Rock-salt equation of state, PBE."
    assert len(first.attrs["source_sha256"]) == 64 and first.properties["energy"] == -6.7
    assert first.status == "new" and not result.skipped


def test_incar_parsing(tmp_path):
    path = tmp_path / "INCAR"
    path.write_text(
        "ENCUT = 520 # cutoff\nISMEAR = 0 ; SIGMA = 0.05\nGGA=PE\n! comment\nLDAU = .TRUE.\n"
    )
    assert parse_incar(path) == {
        "ENCUT": 520,
        "ISMEAR": 0,
        "SIGMA": 0.05,
        "GGA": "PE",
        "LDAU": ".TRUE.",
    }


def test_plan_apply_is_reviewed_atomic_and_incremental(project, tmp_path):
    target = tmp_path / "group.usifc"
    plan = plan_from_scan(target, scan_directory(project, group="/eos").candidates)
    saved = Plan.load(plan.save(tmp_path / "plan.json"))
    assert saved.id == plan.id and [op.frame for op in saved.operations] == [0, 0]
    assert not target.exists()  # building and saving a plan writes nothing
    report = apply_plan(saved)
    assert report.counts["add"] == 2
    with Dataset(target, "r") as data:
        entry = data.entry("/eos/salts/scan/a560")
        assert entry.attrs["plan"] == plan.id and data.count(Q.attr("plan") == plan.id) == 2
    # Scanning again finds nothing new; the same plan cannot be applied twice.
    again = scan_directory(project, group="/eos", dataset=target)
    assert {c.status for c in again.candidates} == {"registered"}
    assert len(plan_from_scan(target, again.candidates)) == 0
    with pytest.raises(AgentError, match="already exists"):
        apply_plan(saved)
    # A changed source is a conflict; the plan refuses to run if the file changes again.
    io.write(nacl(5.6, -6.9), project / "salts" / "scan" / "a560.usif")
    changed = scan_directory(project, group="/eos", dataset=target)
    assert sorted(c.status for c in changed.candidates) == ["conflict", "registered"]
    update = plan_from_scan(target, changed.candidates, update=True)
    assert [op.overwrite for op in update.operations] == [True]
    io.write(nacl(5.6, -7.0), project / "salts" / "scan" / "a560.usif")
    before = target.read_bytes()
    with pytest.raises(AgentError, match="changed since the plan was made"):
        apply_plan(update)
    assert target.read_bytes() == before


def test_plans_reject_edits_and_bad_operations(tmp_path):
    plan = Plan(tmp_path / "d.usifc", [Operation("set_group_attrs", "/g", {"a": 1})])
    data = plan.to_dict()
    data["operations"][0]["attrs"] = {"a": 2}
    with pytest.raises(AgentError, match="does not match"):
        Plan.from_dict(data)
    del data["id"]
    assert Plan.from_dict(data).operations[0].attrs == {"a": 2}
    with pytest.raises(AgentError, match="unknown plan operation"):
        Operation("drop_table", "/x")
    with pytest.raises(AgentError, match="sha256"):
        Operation("add", "/x/y", source="f.usif")
    with pytest.raises(AgentError, match="no such entry"):
        apply_plan(Plan(tmp_path / "d.usifc", [Operation("remove", "/g/missing")]))


# -- tools and the conversation loop ---------------------------------------------------------


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / "group.usifc"
    with Dataset(path) as data:
        data.add(nacl(), "nacl", "/salts", {"notes": "reference rock salt", "code": "vasp"})
        data.add(
            Structure([8, 1, 1], [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]]), "h2o", "/mol"
        )
    return path


def test_tools_read_and_only_propose(dataset, project):
    tools = Toolbox(dataset, roots=[project])
    before = dataset.read_bytes()
    found = json.loads(tools.call("search_entries", {"elements": ["Na"], "text": "ROCK"}))
    assert [e["path"] for e in found["entries"]] == ["/salts/nacl"]
    assert found["entries"][0]["properties"]["energy"] == -6.8
    found = json.loads(
        tools.call("search_entries", {"properties": [{"name": "energy", "op": "<", "value": -7}]})
    )
    assert found["returned"] == 0
    assert json.loads(tools.call("get_entry", {"path": "/salts/nacl"}))["cell"]["volume"] > 0
    assert "error" in json.loads(tools.call("get_entry", {"path": "/salts/none"}))
    assert "outside" in json.loads(tools.call("inspect_file", {"path": "/etc/hostname"}))["error"]
    scanned = json.loads(tools.call("scan_directory", {"path": str(project), "group": "/eos"}))
    assert scanned["new"] == 2
    proposed = json.loads(tools.call("propose_import", {"scan_id": 0, "reason": "new runs"}))
    assert len(proposed["proposed"]) == 2 and "Nothing was written" in proposed["note"]
    tools.call("propose_entry_attrs", {"path": "/salts/nacl", "attrs": {"tag": "ref"}})
    tools.call("propose_remove", {"path": "/mol/h2o", "reason": "duplicate"})
    assert "error" in json.loads(tools.call("propose_remove", {"path": "/mol/h2o"}))
    assert "error" in json.loads(tools.call("no_such_tool", {}))
    assert dataset.read_bytes() == before and len(tools.plan) == 4
    apply_plan(tools.plan)
    with Dataset(dataset, "r") as data:
        assert len(data) == 3 and data.entry("/salts/nacl").attrs["tag"] == "ref"


class ScriptedModel:
    """Returns prepared assistant messages and records what it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def complete(self, messages, tools):
        self.seen.append([dict(m) for m in messages])
        return self.replies.pop(0)


def call(name, arguments, id="c1"):
    return {
        "id": id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def test_session_runs_tools_and_collects_a_plan(dataset):
    model = ScriptedModel(
        [
            {"content": "", "tool_calls": [call("search_entries", {"formula": "NaCl"})]},
            {
                "content": "",
                "reasoning_content": "thinking",
                "tool_calls": [
                    call("propose_entry_attrs", {"path": "/salts/nacl", "attrs": {"x": 1}}, "c2"),
                    {"id": "c3", "function": {"name": "show_plan", "arguments": "not json"}},
                ],
            },
            {"content": "Proposed one change."},
        ]
    )
    seen_tools = []
    session = Session(model, Toolbox(dataset), on_tool=lambda n, a: seen_tools.append(n))
    assert session.ask("tag the NaCl entry") == "Proposed one change."
    assert seen_tools == ["search_entries", "propose_entry_attrs"]
    tool_messages = [m for m in session.messages if m["role"] == "tool"]
    assert json.loads(tool_messages[0]["content"])["entries"][0]["path"] == "/salts/nacl"
    assert "not a JSON object" in tool_messages[2]["content"]
    assert session.plan.request == "tag the NaCl entry" and len(session.plan) == 1
    assert (
        "/salts/nacl" in model.seen[0][0]["content"] or str(dataset) in model.seen[0][0]["content"]
    )
    loop = ScriptedModel([{"tool_calls": [call("show_plan", {})]}] * 3)
    with pytest.raises(AgentError, match="no answer"):
        Session(loop, Toolbox(dataset), max_steps=3).ask("loop")


def test_missing_dataset_is_reported_to_the_model(tmp_path):
    tools = Toolbox(tmp_path / "new.usifc")
    assert json.loads(tools.call("dataset_overview", {}))["exists"] is False
    assert "does not exist yet" in json.loads(tools.call("search_entries", {}))["error"]


def test_redirects_are_refused_and_bad_keys_never_echoed(monkeypatch):
    request = urllib.request.Request("https://api.deepseek.com/chat/completions")
    with pytest.raises(urllib.error.HTTPError, match="refused"):
        llm._NoRedirect().redirect_request(request, None, 302, "Found", {}, "http://evil.example")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-abc\r\nX-Evil: 1")
    with pytest.raises(AgentError) as info:
        load_config().api_key()
    assert "control characters" in str(info.value) and "sk-abc" not in str(info.value)


def test_scan_never_follows_links_out_of_the_root(project, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / ".env").write_text("DEEPSEEK_API_KEY = sk-secret\n")
    io.write(nacl(), outside / "x.usif")
    calc = project / "calc"
    calc.mkdir()
    io.write(nacl(6.0), calc / "real.usif")
    (calc / "INCAR").symlink_to(outside / ".env")
    (calc / "linked.usif").symlink_to(outside / "x.usif")
    (project / "linkdir").symlink_to(outside, target_is_directory=True)
    result = scan_directory(project, group="/g")
    sources = {str(c.source) for c in result.candidates}
    assert not any("outside" in s for s in sources)
    assert all("sk-secret" not in json.dumps(c.attrs) for c in result.candidates)


def test_colliding_entry_paths_are_renamed(tmp_path):
    root = tmp_path / "p"
    (root / "calc").mkdir(parents=True)
    io.write(nacl(5.5), root / "calc.usif")
    io.write(nacl(5.6), root / "calc.json")
    result = scan_directory(root, group="/g")
    assert sorted(c.path for c in result.candidates) == ["/g/calc", "/g/calc.usif"] or sorted(
        c.path for c in result.candidates
    ) == ["/g/calc.json", "/g/calc.usif"]
    assert len(plan_from_scan(tmp_path / "d.usifc", result.candidates)) == 2


def test_same_content_in_two_places_is_two_calculations(tmp_path):
    for name in ("a", "b"):
        (tmp_path / "p" / name).mkdir(parents=True)
        io.write(nacl(), tmp_path / "p" / name / "in.usif")
    target = tmp_path / "d.usifc"
    first = scan_directory(tmp_path / "p" / "a", group="/g")
    apply_plan(plan_from_scan(target, first.candidates))
    both = scan_directory(tmp_path / "p", group="/g", dataset=target)
    assert sorted(c.status for c in both.candidates) == ["new", "registered"]


def test_display_escapes_model_text_and_shows_values(tmp_path):
    op = Operation("set_group_attrs", "/g", {"description": "x\x1b[8m"}, note="ok\n  remove /all")
    plan = Plan(tmp_path / "d.usifc", [op], request="hi\x1b[2J")
    text = plan.describe()
    assert "\x1b" not in text and "\n  remove" not in text and "description" in text
    assert "\\u001b[8m" in text and "hi\\x1b[2J" in text  # escaped, visible to the reviewer
    for bad in (
        {"op": "add", "target": "/g/x", "source": "f", "sha256": "0" * 64, "frame": -1},
        {"op": "add", "target": "/g/x", "source": "f", "sha256": "0" * 64, "overwrite": "false"},
        {"op": "add", "target": "/g/x", "source": "f", "sha256": "nothex"},
        {"op": "set_group_attrs", "target": "/g//../x"},
        {"op": "set_attrs", "target": "/g/", "attrs": {}},
        {"op": "set_attrs", "target": "/g/x", "attrs": [1]},
    ):
        with pytest.raises(AgentError):
            Operation.from_dict(bad)
    with pytest.raises(AgentError):
        Plan.from_dict({"format": "usif.agent.plan.v1", "dataset": "d", "operations": [1]})


def test_add_remove_add_is_a_valid_sequence(tmp_path):
    plan = Plan(tmp_path / "d.usifc")
    add = Operation("add", "/g/x", source="f", sha256="0" * 64)
    plan.add(add)
    plan.add(Operation("remove", "/g/x"))
    plan.add(add)
    with pytest.raises(AgentError, match="already creates or removes"):
        plan.add(add)
    with pytest.raises(AgentError, match="already creates or removes"):
        plan.add(Operation("link", "/g/x", source="/g/y"))


def test_failed_tool_calls_leave_the_plan_unchanged(dataset, project):
    tools = Toolbox(dataset, roots=[project])
    tools.call("scan_directory", {"path": str(project), "group": "/eos"})
    for args in ({"scan_id": 0, "indices": [99]}, {"scan_id": 0, "indices": [-1]}):
        assert "indices" in json.loads(tools.call("propose_import", args))["error"]
    assert "error" in json.loads(tools.call("search_entries", {"properties": ["x"]}))
    assert len(tools.plan) == 0


def test_apply_reports_bad_frames_cleanly(project, tmp_path):
    candidate = scan_directory(project, group="/g").candidates[0]
    op = Operation("add", "/g/x", source=str(candidate.source), sha256=candidate.sha256, frame=5)
    with pytest.raises(AgentError, match="no frame 5"):
        apply_plan(Plan(tmp_path / "d.usifc", [op]))


# -- projects: create, save into, query ---------------------------------------------------


def test_create_a_project_in_a_new_dataset(tmp_path):
    path = tmp_path / "new.usifc"
    tools = Toolbox(path)
    assert json.loads(tools.call("list_projects", {}))["dataset_exists"] is False
    bad = json.loads(tools.call("propose_project", {"name": "a/b", "description": "x"}))
    assert "one path component" in bad["error"]
    assert "description" in json.loads(tools.call("propose_project", {"name": "oer"}))["error"]
    made = json.loads(
        tools.call(
            "propose_project",
            {"name": "oer", "description": "OER perovskites", "attrs": {"owner": "li"}},
        )
    )
    assert made["project_group"] == "/projects/oer" and made["dataset_exists"] is False
    options = json.loads(tools.call("propose_storage_options", {"compression": "lzma"}))
    assert options["options"] == {"compression": "lzma"}
    assert "error" in json.loads(tools.call("propose_storage_options", {"symmetry": "maybe"}))
    assert "error" in json.loads(tools.call("propose_storage_options", {"precision": "f32"}))
    assert json.loads(tools.call("list_projects", {}))["proposed"] == ["/projects/oer"]
    text = tools.plan.describe()
    assert "options for added structures: compression=lzma" in text
    assert not path.exists()  # proposing writes nothing
    apply_plan(Plan.from_dict(tools.plan.to_dict()))
    listed = json.loads(Toolbox(path).call("list_projects", {}))["projects"]
    assert listed == [
        {
            "project": "oer",
            "group": "/projects/oer",
            "entries": 0,
            "attrs": {"owner": "li", "description": "OER perovskites"},
        }
    ]


def test_save_search_results_into_a_project(tmp_path):
    path = tmp_path / "group.usifc"
    with Dataset(path) as data:
        data.add(nacl(5.6, -6.7), "relax", "/oer/SrTiO3", {"code": "vasp"})
        data.add(nacl(5.7, -6.9), "relax", "/oer/BaTiO3", {"code": "vasp"})
        data.add(nacl(5.8, -5.0), "relax", "/other")
        records = data.stats()["records"]
    before = path.read_bytes()
    tools = Toolbox(path)
    tools.call("propose_project", {"name": "low", "description": "low-energy salts"})
    low = {"properties": [{"name": "energy", "op": "<", "value": -6.5}]}
    saved = json.loads(
        tools.call("propose_link", {"group": "/projects/low", "filters": low, "reason": "E<-6.5"})
    )
    assert saved["proposed"] == [
        "link      /projects/low/SrTiO3/relax  <-  /oer/SrTiO3/relax  (E<-6.5)",
        "link      /projects/low/BaTiO3/relax  <-  /oer/BaTiO3/relax  (E<-6.5)",
    ]
    again = json.loads(tools.call("propose_link", {"group": "/projects/low", "filters": low}))
    assert again["proposed"] == []
    assert {s["reason"] for s in again["skipped"]} == {"already saved there"}
    clash = json.loads(
        tools.call("propose_link", {"group": "/projects/low/SrTiO3", "paths": ["/other/relax"]})
    )
    assert clash["proposed"] == [] and clash["skipped"][0]["reason"] == "path taken"
    for bad in (
        {"group": "/projects/low"},
        {"group": "/projects/low", "paths": ["/oer/SrTiO3/relax"], "filters": low},
        {"group": "/", "paths": ["/oer/SrTiO3/relax"]},
        {"group": "/projects/low", "filters": {"colour": "red"}},
        {"group": "/projects/low", "paths": ["/oer/none"]},
    ):
        assert "error" in json.loads(tools.call("propose_link", bad)), bad
    assert len(tools.plan) == 3 and path.read_bytes() == before
    apply_plan(tools.plan)
    with Dataset(path, "r") as data:
        assert data.stats()["records"] == records  # linked, not copied
        entry = data.entry("/projects/low/BaTiO3/relax")
        assert entry.attrs["linked_from"] == "/oer/BaTiO3/relax" and entry.attrs["code"] == "vasp"
        assert entry.attrs["plan"] == tools.plan.id
        assert entry.record_hash == data.entry("/oer/BaTiO3/relax").record_hash
    found = json.loads(Toolbox(path).call("search_entries", {"group": "/projects/low"}))
    assert found["returned"] == 2
    listed = json.loads(Toolbox(path).call("list_projects", {}))["projects"]
    assert [(p["project"], p["entries"]) for p in listed] == [("low", 2)]
    repeat = Toolbox(path)
    result = json.loads(
        repeat.call(
            "propose_link",
            {
                "group": "/projects/low",
                "paths": ["/oer/BaTiO3/relax", "/projects/low/SrTiO3/relax"],
            },
        )
    )
    assert result["proposed"] == [] and {s["reason"] for s in result["skipped"]} == {
        "already saved there",
        "already in the group",
    }


def test_link_operations_are_checked(tmp_path):
    path = tmp_path / "d.usifc"
    with Dataset(path) as data:
        data.add(nacl(), "a", "/g")
    for bad in (
        {"op": "link", "target": "/p/a"},
        {"op": "link", "target": "/p/a", "source": "g/a"},
        {"op": "link", "target": "/p/a", "source": "/p/a"},
        {"op": "link", "target": "/p/a", "source": "/g/a", "sha256": "0" * 64},
        {"op": "link", "target": "/p/a", "source": "/g/a", "overwrite": True},
    ):
        with pytest.raises(AgentError):
            Operation.from_dict(bad)
    with pytest.raises(AgentError, match="source entry /g/none does not exist"):
        apply_plan(Plan(path, [Operation("link", "/p/a", source="/g/none")]))
    with pytest.raises(AgentError, match="already exists"):
        apply_plan(Plan(path, [Operation("link", "/g/a", source="/g/a2")]))
    removed = Plan(path, [Operation("remove", "/g/a"), Operation("link", "/p/a", source="/g/a")])
    with pytest.raises(AgentError, match="does not exist"):
        apply_plan(removed)
    chained = Plan(path, [Operation("link", "/p/a", source="/g/a")])
    chained.add(Operation("link", "/q/a", source="/p/a", attrs={"tag": "x"}))
    assert "link      /q/a  <-  /p/a  {" in chained.describe()
    assert apply_plan(Plan.load(chained.save(tmp_path / "plan.json"))).counts["link"] == 2
    with Dataset(path, "r") as data:
        assert data.entry("/q/a").attrs["linked_from"] == "/p/a"
        assert data.entry("/q/a").attrs["tag"] == "x"


def test_session_creates_a_project_from_plain_words(tmp_path):
    model = ScriptedModel(
        [
            {"tool_calls": [call("list_projects", {})]},
            {
                "tool_calls": [
                    call("propose_project", {"name": "eos", "description": "NaCl EOS"}, "c2")
                ]
            },
            {"content": "Proposed the project /projects/eos."},
        ]
    )
    session = Session(model, Toolbox(tmp_path / "new.usifc"))
    assert "does not exist yet" in session.messages[0]["content"]
    assert session.ask("start a project for the NaCl EOS") == "Proposed the project /projects/eos."
    assert [op.target for op in session.plan.operations] == ["/projects/eos"]
    assert not (tmp_path / "new.usifc").exists()
