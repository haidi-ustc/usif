"""Projects in plain words: the agent creates a project, saves search results into it, queries it.

A scripted model stands in for the LLM, so this runs offline and without an API key. With a real
model the same requests go through ``usif agent ask DATASET "..."``; the tools, the plan and the
approval step are identical.
"""

import json
import tempfile
from pathlib import Path

from usif import Cell, Dataset, Q, Structure
from usif.agent import Plan, Session, Toolbox, apply_plan


def perovskite(symbol: str, a: float, energy: float) -> Structure:
    return Structure.from_fractional(
        [symbol, "Ti", "O", "O", "O"],
        [[0, 0, 0], [0.5] * 3, [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]],
        Cell.cubic(a),
        properties={"energy": energy},
    )


class ScriptedModel:
    """Replays what an LLM would answer: lists of tool calls, then a text reply."""

    def __init__(self, steps):
        self.steps = list(steps)

    def complete(self, messages, tools):
        step = self.steps.pop(0)
        if isinstance(step, str):
            return {"content": step}
        calls = [
            {"id": f"call{i}", "function": {"name": name, "arguments": json.dumps(args)}}
            for i, (name, args) in enumerate(step)
        ]
        return {"content": "", "tool_calls": calls}


with tempfile.TemporaryDirectory() as tmp:
    dataset = Path(tmp) / "lab.usifc"
    with Dataset(dataset) as data:  # what earlier imports left in the dataset
        data.add(perovskite("Sr", 3.905, -40.1), "relax", "/oer/SrTiO3", {"code": "vasp"})
        data.add(perovskite("Ba", 4.000, -41.2), "relax", "/oer/BaTiO3", {"code": "vasp"})
        data.add(perovskite("Ca", 3.840, -38.9), "relax", "/oer/CaTiO3", {"code": "vasp"})

    low = {"properties": [{"name": "energy", "op": "<", "value": -40}]}
    model = ScriptedModel(
        [
            [("list_projects", {}), ("search_entries", low)],
            [
                ("propose_project", {"name": "stable", "description": "Low-energy titanates"}),
                ("propose_link", {"group": "/projects/stable", "filters": low}),
            ],
            "Proposed the project /projects/stable with 2 entries (energy < -40 eV).",
            [("search_entries", {"group": "/projects/stable"})],
            "The project holds /projects/stable/SrTiO3/relax and /projects/stable/BaTiO3/relax.",
        ]
    )
    session = Session(model, Toolbox(dataset))

    # 1. A request in plain words: the agent searches and proposes; nothing is written.
    print(session.ask("Create a project for the low-energy titanates and save them into it."))
    print(session.plan.describe())

    # 2. A person approves the plan (usif agent ask prompts [y/N]); then it is applied.
    saved = session.plan.save(Path(tmp) / "plan.json")
    report = apply_plan(Plan.load(saved))
    print(f"Applied: {report.counts['set_group_attrs']} project, {report.counts['link']} links")

    # 3. Ask about it: questions only read, so no plan is proposed.
    session.toolbox.plan = Plan(str(dataset))
    print(session.ask("Which entries are in the stable project?"))
    found = json.loads(session.messages[-2]["content"])  # the search tool's real result
    print(f"Search tool found: {[e['path'] for e in found['entries']]}")
    print(f"Proposed by the question: {len(session.plan)} changes")

    # 4. The same data from Python.
    with Dataset(dataset, "r") as data:
        members = [e.path for e in data.query(Q.group("/projects/stable"))]
        print(f"Project entries: {members}")
        print(f"Project description: {data.group_attrs('/projects/stable')['description']}")
        print(f"Records stored: {data.stats()['records']} (links copy nothing)")
    projects = json.loads(Toolbox(dataset).call("list_projects", {}))["projects"]
    print(f"Projects: {[(p['project'], p['entries']) for p in projects]}")
