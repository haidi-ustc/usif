"""The ``usif`` command-line interface (Typer) over :mod:`usif.io`, datasets and upgrades.

:func:`main` takes an argv-style list and returns an exit code, so it can be
called from Python and tests; installed users get the ``usif`` console script.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import typer
from typer.main import get_command

from usif import io
from usif.errors import USIFError, ValidationError
from usif.version import (
    DATASET_SCHEMA_VERSION,
    FORMAT_VERSION,
    RELEASE_ID,
    RELEASE_RECORD,
    __version__,
)

#: ``-h`` works everywhere ``--help`` does.
CONTEXT = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    help="USIF tools: inspect, convert, validate and upgrade structures and datasets.",
    context_settings=CONTEXT,
    add_completion=False,
)
dataset_app = typer.Typer(help="Work with .usifc datasets.", context_settings=CONTEXT)
app.add_typer(dataset_app, name="dataset")


@dataset_app.callback(invoke_without_command=True)
def _dataset_root(ctx: typer.Context) -> None:
    """Work with .usifc datasets."""
    if ctx.invoked_subcommand is None:  # bare "usif dataset" shows help, not an error
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


_JSON = typer.Option(False, "--json", help="Print machine-readable JSON.")
_PROP_FILTER = re.compile(r"^\s*([^<>=!\s]+)\s*(<=|>=|==|!=|<|>|=)\s*(\S+)\s*$")


def _print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=str))


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


def _dataset_summary(path: Path) -> Dict[str, Any]:
    from usif.dataset import Dataset
    from usif.upgrade import is_container_v2

    if is_container_v2(path):
        return {"path": str(path), "container_v2": True, "hint": "run 'usif upgrade' to convert"}
    with Dataset(path, "r") as dataset:
        return {
            "path": str(path),
            "schema": DATASET_SCHEMA_VERSION,
            **dataset.stats(),
            "groups": dataset.groups(),
            "metadata": dataset.metadata(),
        }


def _echo_summary(data: Dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, dict):
            value = ", ".join(f"{k}={v}" for k, v in value.items()) or "-"
        elif isinstance(value, list):
            value = ", ".join(map(str, value)) or "-"
        typer.echo(f"{key:>16}: {value}")


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show the package version and exit."),
) -> None:
    """USIF tools: inspect, convert, validate and upgrade structures and datasets."""
    if version:
        typer.echo(f"USIF {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command("version")
def version_command(json_output: bool = _JSON) -> None:
    """Show the package, release and file-format versions."""
    data = {
        "version": __version__,
        "format_version": FORMAT_VERSION,
        "dataset_schema": DATASET_SCHEMA_VERSION,
        "release_record": RELEASE_RECORD,
        "release_id": RELEASE_ID,
    }
    if json_output:
        _print_json(data)
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
    json_output: bool = _JSON,
) -> None:
    """Summarise a structure file or dataset."""
    data = _dataset_summary(path) if _is_dataset(path) else _structure_summary(path)
    if json_output:
        _print_json(data)
    else:
        _echo_summary(data)


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
    json_output: bool = _JSON,
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
        _print_json({"path": str(path), "ok": not errors, "errors": errors})
    else:
        typer.echo(f"{path}: {'ok' if not errors else 'INVALID'}")
        for error in errors:
            typer.echo(f"  {error}")
    if errors:
        raise typer.Exit(1)


@app.command("upgrade")
def upgrade_command(
    source: Path = typer.Argument(
        ..., metavar="SOURCE", help="A format-5/6 .usif record or a v2 .usifc container."
    ),
    target: Path = typer.Argument(
        ..., metavar="TARGET", help="Output .usif record or .usifc dataset."
    ),
    symmetry: str = typer.Option("off", help="'auto' stores the asymmetric unit when lossless."),
) -> None:
    """Rewrite a file written by USIF 0.8 or earlier in the current formats."""
    from usif.upgrade import is_container_v2

    if is_container_v2(source):
        from usif.dataset import Dataset

        with Dataset(target, "w", symmetry=symmetry) as dataset:
            count = dataset.import_v2(source)
        typer.echo(f"{source} -> {target}: {count} entries")
        return
    if source.suffix.lower() != ".usif" or target.suffix.lower() != ".usif":
        raise ValidationError("upgrade takes a .usif record or a v2 .usifc container")
    io.write(io.read(source), target, symmetry=symmetry)
    typer.echo(f"{source} -> {target}")


# -- dataset commands ---------------------------------------------------------------


def _query(
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
    json_output: bool = _JSON,
) -> None:
    """List entries matching the filters."""
    from usif.dataset import Dataset

    where = _query(group, formula, chemsys, elements, max_atoms, prop)
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
        _print_json(rows)
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


def _describe(exc: BaseException) -> str:
    """A one-line message for errors reported without a traceback."""
    if isinstance(exc, OSError) and exc.strerror:
        return f"{exc.filename}: {exc.strerror}" if exc.filename else exc.strerror
    if isinstance(exc, KeyError):
        return f"not found: {exc.args[0] if exc.args else ''}"
    return str(exc)


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
        typer.echo(f"usif: error: {_describe(exc)}", err=True)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the console script
    raise SystemExit(main())
