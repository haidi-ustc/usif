"""Size and speed of the record encoding options.

Run from the repository root::

    python -m scripts.benchmark --count 20 --natoms 2000
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import typer

from usif import Cell, Structure, decode, encode
from usif.codec import jsondoc

__all__ = ["DEFAULT_OPTIONS", "benchmark", "synthetic_structures"]

DEFAULT_OPTIONS: Dict[str, Dict[str, Any]] = {
    "none": {"compression": "none"},
    "zlib": {"compression": "zlib"},
    "lzma": {"compression": "lzma"},
    "zlib+f32": {"compression": "zlib", "precision": "f32"},
    "zlib+symmetry": {"compression": "zlib", "symmetry": "auto"},
}


def synthetic_structures(count: int = 20, natoms: int = 2000, seed: int = 0) -> List[Structure]:
    """Random periodic structures with forces, charges and an energy."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(count):
        out.append(
            Structure(
                rng.integers(1, 84, natoms),
                rng.random((natoms, 3)) * 30.0,
                Cell.cubic(30.0),
                arrays={"force": rng.normal(size=(natoms, 3)), "charge": rng.normal(size=natoms)},
                properties={"energy": float(rng.normal()) * natoms},
            )
        )
    return out


def benchmark(
    structures: Sequence[Structure],
    options: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Dict[str, float]]:
    """Bytes per atom and encode/decode throughput (atoms/s) for each option set.

    The ``json`` row is the uncompressed JSON document, as a baseline.
    """
    options = DEFAULT_OPTIONS if options is None else options
    atoms = sum(s.natoms for s in structures) or 1
    results: Dict[str, Dict[str, float]] = {}

    def measure(name: str, enc: Any, dec: Any) -> None:
        start = time.perf_counter()
        blobs = [enc(s) for s in structures]
        encoded = time.perf_counter()
        for blob in blobs:
            dec(blob)
        decoded = time.perf_counter()
        results[name] = {
            "bytes_per_atom": sum(len(b) for b in blobs) / atoms,
            "encode_atoms_per_s": atoms / max(encoded - start, 1e-9),
            "decode_atoms_per_s": atoms / max(decoded - encoded, 1e-9),
        }

    measure("json", lambda s: jsondoc.dumps(s, indent=None).encode(), jsondoc.loads)
    for name, opts in options.items():
        measure(name, lambda s, o=opts: encode(s, **o), decode)
    return results


def _format(results: Mapping[str, Mapping[str, float]]) -> Iterable[str]:
    yield f"{'options':<16}{'B/atom':>10}{'encode atoms/s':>18}{'decode atoms/s':>18}"
    for name, row in results.items():
        yield (
            f"{name:<16}{row['bytes_per_atom']:>10.1f}"
            f"{row['encode_atoms_per_s']:>18,.0f}{row['decode_atoms_per_s']:>18,.0f}"
        )


def main(
    count: int = typer.Option(20, help="Number of synthetic structures."),
    natoms: int = typer.Option(2000, help="Atoms per structure."),
    seed: int = typer.Option(0, help="Random seed."),
) -> None:
    """Print bytes per atom and throughput for each encoding option."""
    for line in _format(benchmark(synthetic_structures(count, natoms, seed))):
        typer.echo(line)


if __name__ == "__main__":
    app = typer.Typer(
        add_completion=False, context_settings={"help_option_names": ["-h", "--help"]}
    )
    app.command()(main)
    app()
