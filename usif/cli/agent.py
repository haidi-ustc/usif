"""``usif agent``: the LLM data agent and saved change plans.

The agent only proposes changes; :func:`usif.cli.plans.review` applies them
after a person approves.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from usif.cli.common import JSON_OPTION, command_group, echo_summary, print_json
from usif.cli.plans import review, save_pending
from usif.errors import USIFError, ValidationError

agent_app = command_group(
    "Ask the data agent (an LLM) about a dataset; it proposes changes for you to approve."
)


def terminal_text(text: str) -> str:
    """Model output with control characters escaped (line breaks and tabs kept).

    An answer could otherwise carry terminal escape sequences that hide or
    rewrite the change plan printed after it.
    """
    return "".join(
        (
            c
            if c in "\n\t" or unicodedata.category(c)[0] != "C"
            else c.encode("unicode_escape").decode("ascii")
        )
        for c in text
    )


def _session(
    dataset_path: Optional[Path], allow: List[Path], model: Optional[str], base_url: Optional[str]
) -> Any:
    from usif.agent import ChatClient, Session, Toolbox, load_config
    from usif.agent.config import agent_dataset

    dataset = agent_dataset(dataset_path)
    config = load_config({"model": model, "base_url": base_url})
    config.api_key()  # fail early, before the first question
    toolbox = Toolbox(dataset, roots=allow or [Path.cwd()])

    def on_tool(name: str, arguments: Dict[str, Any]) -> None:
        shown = json.dumps(arguments, ensure_ascii=False)
        typer.echo(f"  [{name}] {shown[:160]}", err=True)

    return Session(ChatClient(config), toolbox, on_tool=on_tool)


_ALLOW = typer.Option(
    [], "--allow", help="Directory the agent may read and scan (repeatable; default: current)."
)
_MODEL = typer.Option(None, "--model", help="Model name (default from configuration).")
_BASE_URL = typer.Option(None, "--base-url", help="OpenAI-compatible endpoint URL.")
_DATASET_HELP = (
    "The .usifc dataset. Default: $USIF_DATASET, else the 'dataset' setting of the agent "
    "table in ~/.usif/config.toml (it must exist). A new dataset needs an explicit path."
)


@agent_app.command("ask")
def agent_ask(
    first: Optional[str] = typer.Argument(
        None, metavar="DATASET", help=_DATASET_HELP, show_default=False
    ),
    second: Optional[str] = typer.Argument(
        None, metavar="REQUEST", help="What you want, in plain words.", show_default=False
    ),
    allow: List[Path] = _ALLOW,
    plan_out: Optional[Path] = typer.Option(None, "--plan-out", help="Save proposed changes here."),
    model: Optional[str] = _MODEL,
    base_url: Optional[str] = _BASE_URL,
) -> None:
    """Ask one question or give one instruction; proposed changes need your approval.

    DATASET may be left out when a default dataset is configured: USIF_DATASET,
    else 'dataset' in the agent table of ~/.usif/config.toml.
    """
    if first is None:
        raise typer.BadParameter("missing REQUEST", param_hint="REQUEST")
    if second is None and first.lower().endswith(".usifc") and not any(c.isspace() for c in first):
        # One word naming a dataset is a DATASET without a request, not a request.
        raise typer.BadParameter(
            f"missing REQUEST after DATASET {first}: say what you want, in quotes",
            param_hint="REQUEST",
        )
    dataset_path, request = (None, first) if second is None else (Path(first), second)
    session = _session(dataset_path, allow, model, base_url)
    typer.echo(terminal_text(session.ask(request)))
    if len(session.plan):
        typer.echo("")
        review(session.plan, yes=False, plan_out=plan_out)


@agent_app.command("chat")
def agent_chat(
    dataset_path: Optional[Path] = typer.Argument(
        None, metavar="DATASET", help=_DATASET_HELP, show_default=False
    ),
    allow: List[Path] = _ALLOW,
    model: Optional[str] = _MODEL,
    base_url: Optional[str] = _BASE_URL,
) -> None:
    """Talk to the agent. /plan shows proposals, /apply approves them, /quit ends.

    DATASET may be left out when a default dataset is configured: USIF_DATASET,
    else 'dataset' in the agent table of ~/.usif/config.toml.
    """
    session = _session(dataset_path, allow, model, base_url)
    typer.echo(f"usif agent on {session.toolbox.dataset} ({session.model.config.model})")
    typer.echo("Commands: /plan  /apply  /save FILE  /discard  /quit")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo("")
            line = "/quit"
        if not line:
            continue
        command, _, argument = line.partition(" ")
        if command in ("/quit", "/exit"):
            if len(session.plan):
                saved = save_pending(session.plan)
                typer.echo(f"unapproved plan saved to {saved} (usif agent apply {saved})")
            return
        if command == "/plan":
            typer.echo(session.plan.describe())
        elif command == "/discard":
            session.plan.operations.clear()
            typer.echo("plan discarded")
        elif command == "/save":
            saved = session.plan.save(Path(argument)) if argument else save_pending(session.plan)
            typer.echo(f"plan saved to {saved}")
        elif command == "/apply":
            try:
                if review(session.plan, yes=False, plan_out=None):
                    session.toolbox.plan = type(session.plan)(str(session.toolbox.dataset))
            except USIFError as exc:
                typer.echo(f"usif: error: {exc}", err=True)
        elif command.startswith("/"):
            typer.echo(f"unknown command {command}")
        else:
            before = len(session.plan)
            try:
                typer.echo(terminal_text(session.ask(line)))
            except USIFError as exc:
                typer.echo(f"usif: error: {exc}", err=True)
                continue
            if len(session.plan) != before:
                typer.echo(
                    f"[{len(session.plan)} proposed changes; /plan to review, /apply to approve]"
                )


@agent_app.command("show")
def agent_show(
    plan_path: Path = typer.Argument(..., metavar="PLAN"), json_output: bool = JSON_OPTION
) -> None:
    """Show a saved change plan."""
    from usif.agent import Plan

    plan = Plan.load(plan_path)
    if json_output:
        print_json(plan.to_dict())
    else:
        typer.echo(plan.describe())


@agent_app.command("apply")
def agent_apply(
    plan_path: Path = typer.Argument(..., metavar="PLAN"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without asking."),
) -> None:
    """Apply a reviewed change plan (all of it, in one transaction)."""
    from usif.agent import Plan

    plan = Plan.load(plan_path)
    if not yes and not sys.stdin.isatty():
        raise ValidationError("not a terminal: pass --yes to approve the plan")
    review(plan, yes=yes, plan_out=None, save=False)


@agent_app.command("plans")
def agent_plans(
    applied: bool = typer.Option(False, "--applied", help="List the journal of applied plans."),
    json_output: bool = JSON_OPTION,
) -> None:
    """List the change plans kept in ~/.usif/plans (pending review, or --applied)."""
    from usif.agent import Plan
    from usif.agent.config import plans_dir

    rows: List[Dict[str, Any]] = []
    for path in sorted(plans_dir(applied).glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            plan = Plan.load(path)
        except USIFError as exc:
            rows.append({"file": str(path), "error": str(exc)})
            continue
        rows.append(
            {
                "file": str(path),
                "id": plan.id,
                "created": plan.created,
                "dataset": plan.dataset,
                "operations": len(plan),
                "request": plan.request[:80],
            }
        )
    if json_output:
        print_json(rows)
        return
    for row in rows:
        if "error" in row:
            typer.echo(f"{row['file']}: {row['error']}")
        else:
            typer.echo(
                f"{row['id']}  {row['created']}  {row['operations']:>4} ops  {row['dataset']}"
                + (f"  \"{row['request']}\"" if row["request"] else "")
            )
    typer.echo(f"{len(rows)} plans in {plans_dir(applied)}")


@agent_app.command("config")
def agent_config(json_output: bool = JSON_OPTION) -> None:
    """Show the settings in effect: LLM, default dataset (the API key only as set or not)."""
    from usif.agent.config import config_path, default_dataset, load_config, usif_home

    found = default_dataset()
    data = {
        **load_config().describe(),
        "dataset": str(found[0]) if found else None,
        "dataset_from": found[1] if found else None,
        "dataset_exists": found[0].is_file() if found else None,
        "usif_home": str(usif_home()),
        "config_file": str(config_path()),
    }
    if json_output:
        print_json(data)
    else:
        echo_summary({key: "-" if value is None else value for key, value in data.items()})
