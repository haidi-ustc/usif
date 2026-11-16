"""Find computational results in project directories and describe them as dataset entries.

Scanning only reads; it never writes. Each structure it finds becomes a
:class:`Candidate`: the entry it would create (group and name derived from the
directory layout), the structure summary, and provenance attributes (absolute
source path, SHA-256 of the file, modification time, code, input parameters,
and the nearest README/NOTES text). Candidates turn into a change plan with
:func:`usif.agent.plan.plan_from_scan`.

* A VASP calculation directory (``vasprun.xml``, ``OUTCAR``, ``CONTCAR`` or
  ``POSCAR``) is one candidate: the final structure of the best output file,
  with ``INCAR`` parameters and the ``KPOINTS`` header.
* Every other file with a structure suffix (``.usif``, ``.json``, ``.cif``,
  ``.xyz``, ``.extxyz``, ``.traj``, ...) is one candidate (its last frame), or
  one per frame with ``all_frames=True``.

Files that cannot be read are reported in :attr:`ScanResult.skipped`.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from usif import io
from usif.dataset import Dataset, Q
from usif.dataset.query import MAX_IN_VALUES, normalize_group
from usif.errors import USIFError
from usif.model.structure import Structure

__all__ = ["Candidate", "ScanResult", "scan"]

VASP_OUTPUTS = ("vasprun.xml", "OUTCAR", "CONTCAR", "POSCAR")
STRUCTURE_SUFFIXES = frozenset(
    {".usif", ".json", ".cif", ".xyz", ".extxyz", ".traj", ".vasp", ".poscar", ".pdb", ".xsf"}
)
NOTE_FILES = ("README.md", "README.txt", "README", "NOTES.md", "NOTES.txt", "notes.md", "notes.txt")
SKIP_DIRS = frozenset({"__pycache__", "node_modules", "site-packages"})
MAX_NOTES = 2000
MAX_PARAMETERS = 200
_INCAR_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")


@dataclass
class Candidate:
    """One structure that could become the dataset entry ``group/name``."""

    source: Path
    group: str
    name: str
    frame: int
    frames: int
    sha256: str
    code: str
    formula: str
    natoms: int
    properties: Dict[str, float]
    attrs: Dict[str, Any]
    status: str = "new"  # new | registered | conflict | duplicate

    @property
    def path(self) -> str:
        return f"{self.group.rstrip('/')}/{self.name}"

    def summary(self) -> Dict[str, Any]:
        return {
            "entry": self.path,
            "source": str(self.source),
            "frame": self.frame,
            "code": self.code,
            "formula": self.formula,
            "natoms": self.natoms,
            "properties": self.properties,
            "status": self.status,
        }


@dataclass
class ScanResult:
    root: Path
    candidates: List[Candidate] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def new(self) -> List[Candidate]:
        return [c for c in self.candidates if c.status == "new"]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(text: str) -> Any:
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return text


def parse_incar(path: Path) -> Dict[str, Any]:
    """``KEY = value`` pairs of a VASP INCAR (comments and ``;`` handled)."""
    params: Dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = re.split(r"[#!]", line, maxsplit=1)[0]
        for part in line.split(";"):
            match = _INCAR_LINE.match(part)
            if match and len(params) < MAX_PARAMETERS:
                params[match.group(1).upper()] = _number(match.group(2))
    return params


def _inside(path: Path, root: Path) -> bool:
    """A regular file that is not a symbolic link and resolves to a place below ``root``.

    Every file the scanner opens passes this check, so links cannot pull in
    files from outside the scanned (and allowed) directory.
    """
    try:
        if path.is_symlink() or not path.is_file():
            return False
        resolved = path.resolve()
    except OSError:
        return False
    return resolved == root or root in resolved.parents


def _notes(directory: Path, root: Path) -> Optional[str]:
    """The nearest README/NOTES text at or above ``directory`` (within ``root``)."""
    current = directory
    while True:
        for name in NOTE_FILES:
            candidate = current / name
            if _inside(candidate, root):
                text = candidate.read_text(encoding="utf-8", errors="replace").strip()
                return text[:MAX_NOTES] if text else None
        if current == root or root not in current.parents:
            return None
        current = current.parent


def _scalar_properties(structure: Structure) -> Dict[str, float]:
    values = {}
    for name in structure.properties:
        raw = structure.properties.raw(name)
        if getattr(raw, "ndim", None) == 0 and raw.dtype.kind in "fiu":
            values[name] = float(raw)
    return values


def _walk(root: Path) -> Iterator[Tuple[Path, List[str]]]:
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS)
        yield Path(current), sorted(f for f in files if not f.startswith("."))


def _group_for(root: Path, directory: Path, prefix: str) -> str:
    rel = directory.relative_to(root).parts
    return normalize_group("/".join((prefix, *rel)))


def scan(
    root: os.PathLike[str] | str,
    *,
    group: str = "/",
    dataset: Optional[os.PathLike[str] | str] = None,
    all_frames: bool = False,
    max_candidates: int = 10000,
    max_file_size: int = 1024**3,
) -> ScanResult:
    """Find computational results under ``root`` (a directory or one file).

    Entries are placed below ``group``: ``root/a/b/calc`` (a VASP directory)
    becomes ``{group}/a/b`` + name ``calc``; ``root/a/x.cif`` becomes
    ``{group}/a`` + name ``x``. With ``dataset``, candidates whose source file
    (same SHA-256 and frame) is already registered are marked ``registered``
    and those whose entry path holds other content ``conflict``.
    """
    base = Path(root).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(2, "No such file or directory", str(root))
    result = ScanResult(base)
    if base.is_file():
        walk: Iterator[Tuple[Path, List[str]]] = iter([(base.parent, [base.name])])
        top = base.parent
    else:
        walk, top = _walk(base), base
    for directory, files in walk:
        vasp = [name for name in VASP_OUTPUTS if name in files and _inside(directory / name, top)]
        if vasp and not base.is_file():
            calc_group = _group_for(top, directory.parent, group) if directory != top else None
            name = directory.name
            _add(
                result,
                directory / vasp[0],
                calc_group or normalize_group(group),
                name,
                "vasp",
                top,
                all_frames,
                max_file_size,
            )
        for filename in files:
            path = directory / filename
            if filename in VASP_OUTPUTS and not base.is_file():
                continue
            if Path(filename.lower()).suffix not in STRUCTURE_SUFFIXES and not base.is_file():
                continue
            if not _inside(path, top):
                continue
            stem = path.stem if sum(Path(f).stem == path.stem for f in files) == 1 else path.name
            _add(
                result,
                path,
                _group_for(top, directory, group),
                stem,
                "file",
                top,
                all_frames,
                max_file_size,
            )
        if len(result.candidates) >= max_candidates:
            result.skipped.append((str(directory), f"stopped after {max_candidates} candidates"))
            break
    _resolve_collisions(result)
    if dataset is not None and Path(dataset).exists():
        _mark_known(result, Path(dataset))
    return result


def _resolve_collisions(result: ScanResult) -> None:
    """Give every candidate its own entry path.

    A VASP directory ``calc/`` and a file ``calc.cif`` next to it, or frame
    names such as ``x-0`` next to a file ``x-0.xyz``, would otherwise share an
    entry. Later candidates are renamed to their full file name (plus the
    frame); what still collides is marked ``duplicate`` and never proposed.
    """
    taken = set()
    for candidate in result.candidates:
        if candidate.path in taken:
            name = candidate.source.name
            if candidate.frames > 1 and name != candidate.name:
                name = f"{name}-{candidate.frame}"
            candidate.name = name
        if candidate.path in taken:
            candidate.status = "duplicate"
            continue
        taken.add(candidate.path)


def _add(
    result: ScanResult,
    path: Path,
    group: str,
    name: str,
    code: str,
    root: Path,
    all_frames: bool,
    max_file_size: int,
) -> None:
    try:
        size = path.stat().st_size
        if size > max_file_size:
            result.skipped.append((str(path), f"larger than {max_file_size} bytes"))
            return
        frames = io.read_all(path)
    except (USIFError, OSError, ValueError) as exc:
        result.skipped.append(
            (str(path), str(exc).splitlines()[0][:300] if str(exc) else repr(exc))
        )
        return
    if not frames:
        result.skipped.append((str(path), "no structures"))
        return
    stat = path.stat()
    common: Dict[str, Any] = {
        "source": str(path),
        "source_sha256": file_sha256(path),
        "source_bytes": stat.st_size,
        "source_modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(
            timespec="seconds"
        ),
    }
    if code != "file":
        common["code"] = code
    directory = path.parent
    if code == "vasp":
        if _inside(directory / "INCAR", root):
            common["incar"] = parse_incar(directory / "INCAR")
        if _inside(directory / "KPOINTS", root):
            lines = (directory / "KPOINTS").read_text(errors="replace").splitlines()[:5]
            common["kpoints"] = "\n".join(line.rstrip() for line in lines)
    notes = _notes(directory, root)
    if notes:
        common["notes"] = notes
    indices = range(len(frames)) if all_frames else [len(frames) - 1]
    for index in indices:
        structure = frames[index]
        entry_name = name if not all_frames or len(frames) == 1 else f"{name}-{index}"
        attrs = {**common, "source_frame": index, "source_frames": len(frames)}
        result.candidates.append(
            Candidate(
                source=path,
                group=group,
                name=entry_name,
                frame=index,
                frames=len(frames),
                sha256=common["source_sha256"],
                code=code,
                formula=structure.reduced_formula,
                natoms=structure.natoms,
                properties=_scalar_properties(structure),
                attrs=attrs,
            )
        )


def _mark_known(result: ScanResult, dataset_path: Path) -> None:
    """Mark candidates already registered (same source file, hash and frame) or whose path is taken.

    Matching includes the source path: two calculation directories holding
    identical input files are still two calculations.
    """
    hashes = sorted({c.sha256 for c in result.candidates})
    registered = set()
    with Dataset(dataset_path, "r") as dataset:
        # One attribute scan per batch of hashes instead of one per candidate.
        for start in range(0, len(hashes), MAX_IN_VALUES):
            batch = Q.attr("source_sha256").isin(hashes[start : start + MAX_IN_VALUES])
            for entry in dataset.query(batch):
                attrs = entry.attrs
                registered.add(
                    (attrs.get("source"), attrs.get("source_sha256"), attrs.get("source_frame"))
                )
        for candidate in result.candidates:
            if candidate.status == "duplicate":
                continue
            if (str(candidate.source), candidate.sha256, candidate.frame) in registered:
                candidate.status = "registered"
            elif candidate.path in dataset:
                candidate.status = "conflict"
