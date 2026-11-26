"""``usif dataset``: add, list, export, compact and import entries of a .usifc dataset."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import typer

from usif import io
from usif.cli.common import JSON_OPTION, command_group, print_json
from usif.cli.plans import review
from usif.errors import ValidationError

dataset_app = command_group("Work with .usifc datasets.")

_PROP_FILTER = re.compile(r"^\s*([^<>=!\s]+)\s*(<=|>=|==|!=|<|>|=)\s*(\S+)\s*$")


def build_query(
    group: Optional[str],
    formula: Optional[str],
    chemsys: Optional[str],
    elements: Optional[str],
    max_atoms: Optional[int],
    props: Sequence[str],
) -> Any:
    from usif.dataset import Q

    where = Q.all()
    if group:
        where &= Q.group(group)
    if formula:
        where &= Q.formula(formula)
    if chemsys:
        where &= Q.chemsys(chemsys)
    if elements:
        where &= Q.elements(*[e for e in elements.split(",") if e])
    if max_atoms is not None:
        where &= Q.natoms(max=max_atoms)
    for text in props:
        match = _PROP_FILTER.match(text)
        if match is None:
            raise ValidationError(f"property filters look like 'energy<-1.5', got {text!r}")
        name, op, raw = match.groups()
        operand = Q.prop(name)
        try:
            value = float(raw)
        except ValueError:
            raise ValidationError(f"property filter {text!r} needs a number") from None
        where &= {
            "<": operand < value,
            "<=": operand <= value,
            ">": operand > value,
            ">=": operand >= value,
            "=": operand == value,
            "==": operand == value,
            "!=": operand != value,
        }[op]
    return where


@dataset_app.command("add")
def dataset_add(
    dataset_path: Path = typer.Argument(..., metavar="DATASET"),
    files: List[Path] = typer.Argument(
        ..., metavar="FILES...", help="Structure files; names default to file stems."
    ),
    group: str = typer.Option("/", help="Group to add to."),
    symmetry: str = typer.Option("off", help="'auto' stores asymmetric units when lossless."),
    compression: str = typer.Option("zlib"),
) -> None:
    """Add structure files (every frame of multi-frame files) to a dataset."""
    from usif.dataset import Dataset

    count = 0
    with Dataset(dataset_path, symmetry=symmetry, compression=compression) as dataset:
        with dataset.transaction():
            for path in files:
                frames = io.read_all(path)
                for index, structure in enumerate(frames):
                    name = path.stem if len(frames) == 1 else f"{path.stem}-{index}"
                    dataset.add(structure, name, group, {"source": path.name}, overwrite=True)
                    count += 1
    typer.echo(f"added {count} structures to {dataset_path}")


@dataset_app.command("list")
def dataset_list(
    dataset_path: Path = typer.Argument(..., metavar="DATASET"),
    group: Optional[str] = typer.Option(None),
    formula: Optional[str] = typer.Option(None, help="Reduced formula, e.g. NaCl."),
    chemsys: Optional[str] = typer.Option(None, help="Exact element set, e.g. Na-Cl."),
    elements: Optional[str] = typer.Option(None, help="Must contain these, e.g. Fe,O."),
    max_atoms: Optional[int] = typer.Option(None),
    prop: List[str] = typer.Option([], help="Numeric filter, e.g. 'energy<-1.5' (repeatable)."),
    limit: Optional[int] = typer.Option(None),
    json_output: bool = JSON_OPTION,
) -> None:
    """List entries matching the filters."""
    from usif.dataset import Dataset

    where = build_query(group, formula, chemsys, elements, max_atoms, prop)
    with Dataset(dataset_path, "r") as dataset:
        rows: List[Dict[str, Any]] = [
            {
                "path": entry.path or f"{entry.group}/<{entry.record_hash[:12]}>",
                "record_hash": entry.record_hash,
                "attrs": entry.attrs,
            }
            for entry in dataset.query(where, limit=limit)
        ]
    if json_output:
        print_json(rows)
        return
    for row in rows:
        typer.echo(f"{row['record_hash'][:16]}  {row['path']}")
    typer.echo(f"{len(rows)} entries")


@dataset_app.command("export")
def dataset_export(
    dataset_path: Path = typer.Argument(..., metavar="DATASET"),
    key: str = typer.Argument(
        ..., metavar="ENTRY", help="Entry path (/group/name) or record hash."
    ),
    output: Path = typer.Argument(..., metavar="OUTPUT"),
) -> None:
    """Write one dataset entry to a structure file."""
    from usif.dataset import Dataset

    with Dataset(dataset_path, "r") as dataset:
        io.write(dataset.get(key), output)
    typer.echo(f"{key} -> {output}")


@dataset_app.command("compact")
def dataset_compact(dataset_path: Path = typer.Argument(..., metavar="DATASET")) -> None:
    """Drop unreferenced records and reclaim space."""
    from usif.dataset import Dataset

    with Dataset(dataset_path) as dataset:
        reclaimed = dataset.compact()
    typer.echo(f"reclaimed {reclaimed} bytes")


@dataset_app.command("import")
def dataset_import(
    source: Path = typer.Argument(
        ..., metavar="SOURCE", help="Project directory (or one file) with calculation results."
    ),
    dataset_path: Path = typer.Argument(..., metavar="DATASET"),
    group: str = typer.Option("/", help="Group to place the entries below."),
    all_frames: bool = typer.Option(False, "--all-frames", help="One entry per frame."),
    update: bool = typer.Option(False, "--update", help="Replace entries whose source changed."),
    symmetry: str = typer.Option("off", help="'auto' stores asymmetric units when lossless."),
    plan_out: Optional[Path] = typer.Option(
        None, "--plan-out", help="Save the change plan (JSON) for review or later apply."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without asking."),
) -> None:
    """Scan a project directory and register its calculations (after confirmation)."""
    from usif.agent import plan_from_scan, scan

    result = scan(source, group=group, dataset=dataset_path, all_frames=all_frames)
    for path, reason in result.skipped:
        typer.echo(f"skipped {path}: {reason}", err=True)
    states = [c.status for c in result.candidates]
    typer.echo(
        f"found {len(states)} structures: {states.count('new')} new, "
        f"{states.count('registered')} already registered, {states.count('conflict')} conflicts"
    )
    options = {"symmetry": symmetry} if symmetry != "off" else {}
    plan = plan_from_scan(
        dataset_path,
        result.candidates,
        update=update,
        options=options,
        origin="usif dataset import",
    )
    review(plan, yes=yes, plan_out=plan_out)
