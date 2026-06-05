"""Typer-powered command-line interface for USIF.

The CLI exposes the stable application services and storage facade without
making the core model depend on command-line concerns.  Programmatic callers may
invoke :func:`main` with an argv-style list; installed users get the ``usif``
console script declared in ``pyproject.toml``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import click
import typer
from typer.main import get_command

from usif.constants import CompressionType
from usif.exceptions import USIFError
from usif.services import load_structure, save_structure, structure_to_json_dict
from usif.storage import StructureContainer
from usif.version import FORMAT_VERSION, RELEASE_ID, RELEASE_RECORD, __version__

_CONTAINER_SUFFIX = ".usifc"

app = typer.Typer(
    help="USIF command-line tools for structures, JSON/USIF conversion, and containers.",
    no_args_is_help=True,
    add_completion=False,
)
container_app = typer.Typer(help="Container-specific commands.", no_args_is_help=True)
app.add_typer(container_app, name="container")


def _json_default(value: Any) -> Any:
    """Best-effort JSON conversion for CLI output values."""
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default))


def _is_container_path(path: Path) -> bool:
    return path.suffix.lower() == _CONTAINER_SUFFIX


def _parse_compression(name: str) -> CompressionType:
    normalized = name.strip().lower()
    if normalized in {"none", "no", "0"}:
        return CompressionType.NONE
    if normalized in {"gzip", "gz", "1"}:
        return CompressionType.GZIP
    raise typer.BadParameter("compression must be one of: none, gzip")


def _format_structure_summary(path: Path, *, include_json: bool = False) -> dict[str, Any]:
    structure = load_structure(path)
    codec_info: dict[str, Any] = {
        "path": str(path),
        "type": "structure",
        "format": "json" if path.name.lower().endswith((".json", ".usif.json")) else "usif",
        "formula": structure.formula,
        "structure_type": structure.structure_type.name.lower(),
        "storage_mode": structure.storage_mode.name.lower(),
        "num_atoms": structure.num_atoms(),
    }
    if include_json:
        codec_info["structure"] = structure_to_json_dict(structure)
    return codec_info


def _format_container_summary(path: Path) -> dict[str, Any]:
    with StructureContainer(path, mode="r") as container:
        stats = container.stats()
        return {
            "path": str(path),
            "type": "container",
            "format": "usifc",
            "stats": stats,
        }


def _show_structure_or_container_summary(data: dict[str, Any]) -> None:
    typer.echo(f"Path: {data['path']}")
    typer.echo(f"Type: {data['type']}")
    typer.echo(f"Format: {data['format']}")
    if data["type"] == "container":
        stats = data["stats"]
        typer.echo(f"Records: {stats['records']}")
        typer.echo(f"Groups: {stats['groups']}")
        typer.echo(f"Formulas: {', '.join(stats['formulas']) if stats['formulas'] else '-'}")
        typer.echo(f"Properties: {', '.join(stats['properties']) if stats['properties'] else '-'}")
        typer.echo(f"File size: {stats['file_size_bytes']} bytes")
    else:
        typer.echo(f"Formula: {data['formula']}")
        typer.echo(f"Structure type: {data['structure_type']}")
        typer.echo(f"Storage mode: {data['storage_mode']}")
        typer.echo(f"Atom count: {data['num_atoms']}")


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show the package version and exit."),
) -> None:
    """USIF command-line tools for structures, JSON/USIF conversion, and containers."""
    if version:
        typer.echo(f"USIF {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command("version")
def version_command(
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Show package, release-record, and binary-format version metadata."""
    data = {
        "version": __version__,
        "format_version": FORMAT_VERSION,
        "release_record": RELEASE_RECORD,
        "release_id": RELEASE_ID,
    }
    if json_output:
        _print_json(data)
    else:
        typer.echo(f"USIF {__version__} ({RELEASE_RECORD}, {RELEASE_ID})")
        typer.echo(f"Binary FORMAT_VERSION: {FORMAT_VERSION}")


@app.command("inspect")
def inspect_command(
    path: Path = typer.Argument(..., help=".usif, .json, .usif.json, or .usifc file to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
    include_structure: bool = typer.Option(
        False,
        "--include-structure",
        help="Include the full JSON structure payload when inspecting a structure file with --json.",
    ),
) -> None:
    """Inspect a structure or container file."""
    data = _format_container_summary(path) if _is_container_path(path) else _format_structure_summary(path, include_json=include_structure)
    if json_output:
        _print_json(data)
    else:
        _show_structure_or_container_summary(data)


@app.command("convert")
def convert_command(
    input_path: Path = typer.Argument(..., metavar="INPUT", help="Input .usif, .json, or .usif.json file."),
    output_path: Path = typer.Argument(..., metavar="OUTPUT", help="Output .usif, .json, or .usif.json file."),
    compression: str = typer.Option("gzip", "--compression", help="USIF compression: gzip or none."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Convert between .usif and official USIF JSON."""
    compression_type = _parse_compression(compression)
    structure = load_structure(input_path)
    save_structure(structure, output_path, compression=compression_type)
    if json_output:
        _print_json({"input": str(input_path), "output": str(output_path), "ok": True})
    else:
        typer.echo(f"Converted {input_path} -> {output_path}")


@app.command("validate")
def validate_command(
    path: Path = typer.Argument(..., help="Structure or .usifc container file to validate."),
    level: str = typer.Option("index", "--level", help="Container validation level: index, records, or full."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Validate a structure or container file."""
    if level not in {"index", "records", "full"}:
        raise typer.BadParameter("level must be one of: index, records, full")

    if _is_container_path(path):
        with StructureContainer(path, mode="r") as container:
            result = container.validate(level=level)
        data: dict[str, Any] = {
            "path": str(path),
            "type": "container",
            "ok": result.ok,
            "level": result.level,
            "errors": result.errors,
            "warnings": result.warnings,
            "structure_count": result.structure_count,
            "group_count": result.group_count,
            "checked_records": result.checked_records,
            "elapsed_seconds": result.elapsed_seconds,
        }
    else:
        try:
            structure = load_structure(path)
            data = {
                "path": str(path),
                "type": "structure",
                "ok": True,
                "formula": structure.formula,
                "num_atoms": structure.num_atoms(),
                "errors": [],
            }
        except Exception as exc:  # noqa: BLE001 - CLI validation returns structured failure output
            data = {"path": str(path), "type": "structure", "ok": False, "errors": [str(exc)]}

    if json_output:
        _print_json(data)
    else:
        typer.echo(f"Validation ok: {data['ok']}")
        typer.echo(f"Type: {data['type']}")
        if data.get("level"):
            typer.echo(f"Level: {data['level']}")
        if data.get("errors"):
            typer.echo("Errors:")
            for error in data["errors"]:
                typer.echo(f"  - {error}")
        if data.get("warnings"):
            typer.echo("Warnings:")
            for warning in data["warnings"]:
                typer.echo(f"  - {warning}")
    if not data["ok"]:
        raise typer.Exit(1)


@container_app.command("stats")
def container_stats_command(
    path: Path = typer.Argument(..., help=".usifc container path."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Show lightweight .usifc statistics."""
    with StructureContainer(path, mode="r") as container:
        stats = container.stats()
    if json_output:
        _print_json(stats)
    else:
        typer.echo(f"Records: {stats['records']}")
        typer.echo(f"Groups: {stats['groups']}")
        typer.echo(f"Unique formulas: {stats['unique_formulas']}")
        typer.echo(f"Properties: {', '.join(stats['properties']) if stats['properties'] else '-'}")
        typer.echo(f"File size: {stats['file_size_bytes']} bytes")


@container_app.command("list")
def container_list_command(
    path: Path = typer.Argument(..., help=".usifc container path."),
    kind: str = typer.Argument(..., help="Index kind: names, formulas, properties, or groups."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """List container indexes."""
    if kind not in {"names", "formulas", "properties", "groups"}:
        raise typer.BadParameter("kind must be one of: names, formulas, properties, groups")
    with StructureContainer(path, mode="r") as container:
        if kind == "names":
            values = container.list_names()
        elif kind == "formulas":
            values = container.list_formulas()
        elif kind == "properties":
            values = container.list_properties()
        else:
            values = container.list_groups()
    if json_output:
        _print_json({kind: values})
    else:
        for value in values:
            typer.echo(value)


def _parse_property_range(values: tuple[str, str, str] | None) -> tuple[str, float, float] | None:
    if not values:
        return None
    name, low, high = values
    return name, float(low), float(high)


def _parse_custom(filters: Iterable[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in filters:
        if "=" not in item:
            raise typer.BadParameter("custom filters must use dotted.path=value")
        key, value = item.split("=", 1)
        result[key] = value
    return result


@container_app.command("query")
def container_query_command(
    path: Path = typer.Argument(..., help=".usifc container path."),
    formula: str | None = typer.Option(None, "--formula", help="Formula equality filter."),
    group: str | None = typer.Option(None, "--group", help="Group path filter."),
    has_property: str | None = typer.Option(None, "--has-property", help="Require a property name."),
    property_range: tuple[str, str, str] | None = typer.Option(
        None,
        "--property-range",
        help="Numeric property range as NAME MIN MAX.",
    ),
    custom: list[str] = typer.Option(
        [],
        "--custom",
        metavar="DOTTED.PATH=VALUE",
        help="Dotted custom-property equality filter; may be repeated.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Query a .usifc container."""
    parsed_property_range = _parse_property_range(property_range)
    parsed_custom = _parse_custom(custom)
    with StructureContainer(path, mode="r") as container:
        results = container.query(
            formula=formula,
            group=group,
            has_property=has_property,
            property_range=parsed_property_range,
            custom=parsed_custom or None,
        )
    data = [
        {"record_hash": record_hash, "formula": structure.formula, "num_atoms": structure.num_atoms()}
        for record_hash, structure in results
    ]
    if json_output:
        _print_json({"count": len(data), "results": data})
    else:
        typer.echo(f"Matches: {len(data)}")
        for item in data:
            typer.echo(f"{item['record_hash']}  {item['formula']}  atoms={item['num_atoms']}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Typer CLI and return a process-style exit code."""
    command = get_command(app)
    try:
        result = command.main(args=list(argv) if argv is not None else None, prog_name="usif", standalone_mode=False)
        return int(result) if isinstance(result, int) else 0
    except (click.ClickException, click.Abort) as exc:
        if isinstance(exc, click.ClickException):
            exc.show(file=sys.stderr)
            return exc.exit_code
        typer.echo("Aborted", err=True)
        return 1
    except typer.Exit as exc:
        return int(exc.exit_code or 0)
    except (USIFError, OSError, ValueError, TypeError) as exc:
        typer.echo(f"usif: error: {exc}", err=True)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through console entry point/tests
    raise SystemExit(main())
