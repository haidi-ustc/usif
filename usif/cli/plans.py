"""Review and apply change plans: the one place where the command line writes a plan.

A plan is applied only after a person approves it (``[y/N]`` on a terminal or
``--yes``); unapproved plans are kept in ``~/.usif/plans`` and applied ones are
moved to the journal in ``~/.usif/plans/applied``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import typer

from usif.cli.common import describe
from usif.errors import USIFError


def review(plan: Any, *, yes: bool, plan_out: Optional[Path], save: bool = True) -> bool:
    """Show a plan and apply it only on explicit approval; returns whether it was applied."""
    from usif.agent import apply_plan

    if not len(plan):
        typer.echo("nothing to change")
        return False
    typer.echo(plan.describe())
    if plan_out is not None:
        typer.echo(f"plan saved to {plan.save(plan_out)}")
    approved = yes or (
        sys.stdin.isatty()
        and typer.confirm(f"Apply these {len(plan)} changes to {plan.dataset}?", default=False)
    )
    if not approved:
        if not save:
            typer.echo("not applied")
            return False
        if plan_out is None:
            plan_out = save_pending(plan)
            typer.echo(f"plan saved to {plan_out}")
        typer.echo(f"not applied; review it, then run: usif agent apply {plan_out}")
        return False
    try:
        report = apply_plan(plan)
    except USIFError:
        if save and plan_out is None:  # keep the reviewed plan for a retry
            typer.echo(f"plan kept in {save_pending(plan)}", err=True)
        raise
    done = ", ".join(f"{n} {k}" for k, n in report.counts.items() if n)
    typer.echo(f"applied plan {report.plan_id} to {report.dataset}: {done}")
    journal(plan)
    return True


def save_pending(plan: Any) -> Path:
    """Keep an unapproved plan in ~/.usif/plans for review."""
    from usif.agent.config import plans_dir

    return Path(plan.save(plans_dir() / f"{plan.id}.json"))


def journal(plan: Any) -> None:
    """Move an applied plan to the journal in ~/.usif/plans/applied."""
    from usif.agent.config import plans_dir

    try:
        plan.save(plans_dir(applied=True) / f"{plan.id}.json")
        (plans_dir() / f"{plan.id}.json").unlink(missing_ok=True)
    except OSError as exc:  # the dataset is already written; the journal is a convenience
        typer.echo(f"usif: warning: plan journal not written: {describe(exc)}", err=True)
