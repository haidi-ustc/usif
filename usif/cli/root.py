"""The ``usif`` command: file commands and :func:`main`; the groups live in sibling modules.

:func:`main` takes an argv-style list and returns an exit code, so it can be
called from Python and tests; installed users get the ``usif`` console script.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import typer
from typer.main import get_command

from usif import io
from usif.cli.agent import agent_app
from usif.cli.common import CONTEXT, JSON_OPTION, describe, echo_summary, print_json
from usif.cli.dataset import dataset_app
from usif.errors import USIFError
from usif.version import (
    DATASET_SCHEMA_VERSION,
    FORMAT_VERSION,
    RELEASE_ID,
    RELEASE_RECORD,
    __version__,
)

app = typer.Typer(
    help="USIF tools: inspect, convert and validate structures and datasets.",
    context_settings=CONTEXT,
    add_completion=False,
)
app.add_typer(dataset_app, name="dataset")
app.add_typer(agent_app, name="agent")


def _is_dataset(path: Path) -> bool:
    return path.suffix.lower() == ".usifc"


def _record_info(path: Path) -> Dict[str, Any]:
    from usif.codec import record
    from usif.upgrade import format6

    data = path.read_bytes()
    if record.is_record(data):
        _, info = record.decode_with_info(data)
        return {
            "format": FORMAT_VERSION,
            "record_hash": info.record_hash,
            "geometry_hash": info.geometry_hash,
            "compression": info.compression,
            "symmetric": info.symmetric,
            "bytes": len(data),
        }
    if format6.is_format6(data):
        _, old = format6.decode_with_info(data)
        return {"format": old.version, "symmetric": old.symmetric, "bytes": len(data)}
    return {}


def _structure_summary(path: Path) -> Dict[str, Any]:
    structure = io.read(path)
    cell = structure.cell
    summary: Dict[str, Any] = {
        "path": str(path),
        "formula": structure.formula,
        "reduced_formula": structure.reduced_formula,
        "natoms": structure.natoms,
        "periodic": structure.is_periodic,
        "arrays": {name: structure.arrays.unit(name) for name in structure.arrays},
        "properties": {name: structure.properties.unit(name) for name in structure.properties},
    }
    if cell is not None:
        summary["cell"] = {
            "lengths": np.round(cell.lengths, 6).tolist(),
            "angles": np.round(cell.angles, 4).tolist(),
            "volume": round(float(cell.volume), 6),
            "pbc": list(cell.pbc),
        }
    if path.suffix.lower() == ".usif":
        summary["record"] = _record_info(path)
    return summary


#: How to bring a USIF 0.8 (version-2) container into a dataset.
HINT_V2 = (
    "a USIF 0.8 container: copy it into a new dataset with "
    "usif.Dataset('new.usifc', 'w').import_v2('old.usifc') (see docs/guide/upgrading.md)"
)


def _dataset_summary(path: Path) -> Dict[str, Any]:
    from usif.dataset import Dataset
    from usif.upgrade import is_container_v2

    if is_container_v2(path):
        return {"path": str(path), "container_v2": True, "hint": HINT_V2}
    with Dataset(path, "r") as dataset:
        return {
            "path": str(path),
            "schema": DATASET_SCHEMA_VERSION,
            **dataset.stats(),
            "groups": dataset.groups(),
            "metadata": dataset.metadata(),
        }


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show the package version and exit."),
) -> None:
    """USIF tools: inspect, convert and validate structures and datasets."""
    if version:
        typer.echo(f"USIF {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command("version")
def version_command(json_output: bool = JSON_OPTION) -> None:
    """Show the package, release and file-format versions."""
    data = {
        "version": __version__,
        "format_version": FORMAT_VERSION,
        "dataset_schema": DATASET_SCHEMA_VERSION,
        "release_record": RELEASE_RECORD,
        "release_id": RELEASE_ID,
    }
    if json_output:
        print_json(data)
    else:
        typer.echo(f"USIF {__version__} ({RELEASE_RECORD}, {RELEASE_ID})")
        typer.echo(f"record format {FORMAT_VERSION}, dataset schema {DATASET_SCHEMA_VERSION}")


@app.command("inspect")
def inspect_command(
    path: Path = typer.Argument(
        ...,
        metavar="PATH",
        help="Structure file (.usif, .json, or any backend format) or .usifc dataset.",
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Summarise a structure file or dataset."""
    data = _dataset_summary(path) if _is_dataset(path) else _structure_summary(path)
    if json_output:
        print_json(data)
    else:
        echo_summary(data)


@app.command("convert")
def convert_command(
    input_path: Path = typer.Argument(..., metavar="INPUT"),
    output_path: Path = typer.Argument(..., metavar="OUTPUT"),
    compression: str = typer.Option("zlib", help="Record compression: none, zlib, lzma, zstd."),
    precision: str = typer.Option("f64", help="Record positions: f64 (exact) or f32."),
    symmetry: str = typer.Option("off", help="'auto' stores the asymmetric unit when lossless."),
    backend: Optional[str] = typer.Option(
        None, help="Backend for non-USIF files (ase, pymatgen, ...)."
    ),
    file_format: Optional[str] = typer.Option(None, "--format", help="Backend file format name."),
) -> None:
    """Convert one structure between any supported file formats."""
    structure = io.read(input_path, format=file_format if backend else None, backend=backend)
    options: Dict[str, Any] = {}
    if output_path.suffix.lower() == ".usif":
        options = {"compression": compression, "precision": precision, "symmetry": symmetry}
    io.write(structure, output_path, backend=backend, format=file_format, **options)
    typer.echo(f"{input_path} -> {output_path}")


@app.command("validate")
def validate_command(
    path: Path = typer.Argument(..., metavar="PATH"),
    full: bool = typer.Option(False, "--full", help="Datasets: decode and re-hash every record."),
    json_output: bool = JSON_OPTION,
) -> None:
    """Check a record or dataset; exit code 1 if it is invalid."""
    errors: List[str] = []
    if _is_dataset(path):
        from usif.dataset import Dataset

        with Dataset(path, "r") as dataset:
            report = dataset.check(full=full)
        errors = report.errors
    else:
        try:
            io.read(path)
        except USIFError as exc:
            errors = [str(exc)]
    if json_output:
        print_json({"path": str(path), "ok": not errors, "errors": errors})
    else:
        typer.echo(f"{path}: {'ok' if not errors else 'INVALID'}")
        for error in errors:
            typer.echo(f"  {error}")
    if errors:
        raise typer.Exit(1)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return a process exit code (2 for USIF errors)."""
    command = get_command(app)
    try:
        command.main(
            args=list(argv) if argv is not None else None, prog_name="usif", standalone_mode=True
        )
    except SystemExit as exc:  # standalone mode reports usage errors and Exit this way
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    except (USIFError, OSError, KeyError) as exc:
        typer.echo(f"usif: error: {describe(exc)}", err=True)
        return 2
    return 0
