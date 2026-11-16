"""Materials Project data for USIF.

Run from the repository root::

    python -m scripts.materials_project download --output-dir mp_data      # needs MP_API_KEY
    python -m scripts.materials_project build mp_data mp.usifc              # JSON -> dataset
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help=__doc__,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def download(
    output_dir: Optional[Path] = typer.Option(None, help="Target directory (default: a temp dir)."),
    api_key: Optional[str] = typer.Option(None, help="API key (default: $MP_API_KEY)."),
    total_entries: int = typer.Option(1000, help="Total number of materials."),
    entries_per_group: int = typer.Option(100, help="Materials per query group."),
    e_above_hull_max: float = typer.Option(0.1, help="Maximum energy above hull, eV/atom."),
    min_band_gap: Optional[float] = typer.Option(None, help="Minimum band gap, eV."),
    max_band_gap: Optional[float] = typer.Option(None, help="Maximum band gap, eV."),
    rate_limit: float = typer.Option(2.0, help="Seconds to wait between query groups."),
    zip_archive: bool = typer.Option(True, "--zip/--no-zip", help="Also write a zip archive."),
) -> None:
    """Download summary documents (with structures) from the Materials Project."""
    key = api_key or os.getenv("MP_API_KEY")
    if not key:
        raise typer.BadParameter("provide --api-key or set MP_API_KEY", param_hint="--api-key")
    from .downloader import download_mp_data

    stats = download_mp_data(
        api_key=key,
        output_dir=None if output_dir is None else str(output_dir),
        total_entries=total_entries,
        entries_per_group=entries_per_group,
        e_above_hull_max=e_above_hull_max,
        min_band_gap=min_band_gap,
        max_band_gap=max_band_gap,
        rate_limit=rate_limit,
        create_zip=zip_archive,
    )
    typer.echo(
        f"downloaded {stats['total_downloaded']} materials, skipped {stats['total_skipped']}"
    )
    for group, count in stats["groups"].items():
        typer.echo(f"  {group}: {count}")
    typer.echo(f"output: {stats.get('output_dir', output_dir)}")
    if "zip_file" in stats:
        typer.echo(f"archive: {stats['zip_file']}")


@app.command()
def build(
    source: Path = typer.Argument(..., help="Directory with group_*/materials.json files."),
    target: Path = typer.Argument(..., help="Dataset (.usifc) to create or extend."),
    group: str = typer.Option("/mp", help="Dataset group for the materials."),
    symmetry: str = typer.Option("off", help="Record symmetry option: off or auto."),
) -> None:
    """Convert downloaded documents into a USIF dataset, one entry per material_id."""
    from usif import Dataset

    from .loader import load_mp_group
    from .mapper import convert_mp_to_usif

    files = sorted(source.glob("group_*/materials.json"))
    if not files:
        raise typer.BadParameter(f"no group_*/materials.json under {source}", param_hint="SOURCE")
    docs = [doc for path in files for doc in load_mp_group(path)]
    with Dataset(target, symmetry=symmetry) as dataset:
        count = dataset.add_many(
            (convert_mp_to_usif(doc) for doc in docs),
            group,
            names=[str(doc["material_id"]) for doc in docs],
        )
    typer.echo(f"added {count} materials to {target}")


if __name__ == "__main__":
    app(prog_name="python -m scripts.materials_project")
