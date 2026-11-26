"""Helpers shared by the ``usif`` command groups: options, output and error messages."""

from __future__ import annotations

import json
from typing import Any, Dict

import typer

#: ``-h`` works everywhere ``--help`` does.
CONTEXT = {"help_option_names": ["-h", "--help"]}

JSON_OPTION = typer.Option(False, "--json", help="Print machine-readable JSON.")


def command_group(help_text: str) -> typer.Typer:
    """A sub-command group whose bare invocation prints its help and exits 0."""
    group = typer.Typer(help=help_text, context_settings=CONTEXT)

    @group.callback(invoke_without_command=True)
    def _show_help(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help())
            raise typer.Exit(0)

    _show_help.__doc__ = help_text
    return group


def print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=str))


def echo_summary(data: Dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, dict):
            value = ", ".join(f"{k}={v}" for k, v in value.items()) or "-"
        elif isinstance(value, list):
            value = ", ".join(map(str, value)) or "-"
        typer.echo(f"{key:>16}: {value}")


def describe(exc: BaseException) -> str:
    """A one-line message for errors reported without a traceback."""
    if isinstance(exc, OSError) and exc.strerror:
        return f"{exc.filename}: {exc.strerror}" if exc.filename else exc.strerror
    if isinstance(exc, KeyError):
        return f"not found: {exc.args[0] if exc.args else ''}"
    return str(exc)
