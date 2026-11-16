"""A group's local dataset: scan project directories, review the plan, apply it, search it."""

import tempfile
from pathlib import Path

from usif import Cell, Dataset, Q, Structure, write
from usif.agent import Plan, apply_plan, plan_from_scan, scan


def rocksalt(a: float, energy: float) -> Structure:
    return Structure.from_fractional(
        ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]], Cell.cubic(a), properties={"energy": energy}
    )


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    # A project directory as people leave it: results in subdirectories, notes in a README.
    project = root / "projects" / "salts"
    for a in (5.5, 5.6, 5.7):
        run = project / "eos" / f"a{a:.2f}"
        run.mkdir(parents=True)
        write(rocksalt(a, 0.5 * (a - 5.64) ** 2 - 6.8), run / "final.usif")
    (project / "README.md").write_text("NaCl equation of state, PBE, 2026.\n")
    dataset = root / "group.usifc"

    # 1. Scan: read-only, nothing is written.
    result = scan(project, group="/salts", dataset=dataset)
    print(f"Found {len(result.candidates)} structures, {len(result.new)} new")

    # 2. A plan to review (and keep, for reproducibility).
    plan = plan_from_scan(dataset, result.candidates)
    print(f"Plan: {len(plan)} operations")
    saved = plan.save(root / "plan.json")

    # 3. After approval, apply it: all operations in one transaction.
    report = apply_plan(Plan.load(saved))
    print(f"Applied: {report.counts['add']} added")

    # 4. Scanning again finds nothing new.
    print(f"New after import: {len(scan(project, group='/salts', dataset=dataset).new)}")

    # 5. Search by structure, properties and provenance.
    with Dataset(dataset, "r") as data:
        low = data.query(Q.formula("NaCl") & (Q.prop("energy") < -6.799))
        print(f"Near the minimum: {[e.path for e in low]}")
        entry = data.entry("/salts/eos/a5.60/final")
        print(f"Notes: {entry.attrs['notes']}")
        print(f"Added by plan: {data.count(Q.attr('plan') == plan.id)}")
