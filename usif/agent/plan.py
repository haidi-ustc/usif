"""Change plans: the only way the agent's work reaches a dataset.

The agent (and ``usif dataset import``) never write to a dataset. They build a
:class:`Plan`, a list of operations on one dataset, which a person reviews and
approves; :func:`apply_plan` then executes it in a single transaction.

A plan is a JSON document (``usif.agent.plan.v1``) that can be saved, read,
edited by hand, and applied later. Its ``id`` is a hash of the dataset path, the
encoding options and the operations, so an applied entry's ``plan`` attribute
identifies exactly what was approved. Before writing, :func:`apply_plan`
re-checks every source file against its recorded SHA-256 and every target
entry against the dataset, and refuses the whole plan if anything changed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from usif import io
from usif.agent.discover import Candidate, file_sha256
from usif.dataset import Dataset
from usif.dataset.query import normalize_group
from usif.errors import AgentError, USIFError
from usif.fileio import atomic_write_text
from usif.model.properties import normalize_json

__all__ = ["OPERATIONS", "PLAN_FORMAT", "ApplyReport", "Operation", "Plan", "apply_plan"]

PLAN_FORMAT = "usif.agent.plan.v1"
#: Operation kinds and what they do.
OPERATIONS = {
    "add": "store the structure of `source` as entry `target`",
    "link": "make entry `target` refer to the record of entry `source` (nothing is copied)",
    "set_attrs": "merge `attrs` into the attributes of entry `target`",
    "set_group_attrs": "merge `attrs` into the attributes of group `target`",
    "remove": "remove entry `target` (its record stays until compact)",
}
_ENCODE_OPTIONS = {"compression", "precision", "symmetry"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_NOTE = 500


def shown(value: Any, limit: int = 300) -> str:
    """Text safe to show a reviewer: control and format characters escaped, length capped.

    Notes, targets and attributes may come from the model; without this an
    escape sequence or a newline could forge or hide lines of the plan.
    """
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = "".join(
        c.encode("unicode_escape").decode("ascii") if unicodedata.category(c)[0] == "C" else c
        for c in text
    )
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _entry_path(path: str) -> str:
    group, _, name = path.rpartition("/")
    if not name or name in (".", "..") or any(unicodedata.category(c)[0] == "C" for c in name):
        raise AgentError(f"invalid entry path {shown(path)}")
    if normalize_group(group or "/") != (group or "/"):
        raise AgentError(f"entry paths look like '/group/name', got {shown(path)}")
    return path


@dataclass(frozen=True)
class Operation:
    """One change. ``target`` is an entry path, or a group path for ``set_group_attrs``."""

    op: str
    target: str
    attrs: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    sha256: Optional[str] = None
    frame: Optional[int] = None
    overwrite: bool = False
    note: str = ""

    def __post_init__(self) -> None:
        """Check every field strictly: plans are also read from hand-edited files."""
        if self.op not in OPERATIONS:
            raise AgentError(f"unknown plan operation {shown(self.op)}")
        if not isinstance(self.target, str) or not self.target.startswith("/"):
            raise AgentError(f"plan targets are '/group/name' paths, got {shown(self.target)}")
        try:
            if self.op == "set_group_attrs":
                if normalize_group(self.target) != self.target:
                    raise AgentError(f"invalid group path {shown(self.target)}")
            else:
                _entry_path(self.target)
            if not isinstance(self.attrs, Mapping):
                raise AgentError("operation attrs must be a JSON object")
            object.__setattr__(self, "attrs", normalize_json(dict(self.attrs), path="attrs"))
        except USIFError as exc:
            raise AgentError(f"{shown(self.target)}: {exc}") from None
        if self.source is not None and not isinstance(self.source, str):
            raise AgentError("operation source must be a path string")
        if self.sha256 is not None and not (
            isinstance(self.sha256, str) and _SHA256.match(self.sha256)
        ):
            raise AgentError("operation sha256 must be 64 lower-case hex digits")
        if self.frame is not None and (
            isinstance(self.frame, bool) or not isinstance(self.frame, int) or self.frame < 0
        ):
            raise AgentError("operation frame must be a non-negative integer")
        if not isinstance(self.overwrite, bool):
            raise AgentError("operation overwrite must be true or false")
        if not isinstance(self.note, str):
            raise AgentError("operation note must be a string")
        object.__setattr__(self, "note", self.note[:MAX_NOTE])
        if self.op == "add" and (self.source is None or self.sha256 is None):
            raise AgentError(f"'add {shown(self.target)}' needs a source file and its sha256")
        if self.op == "link":
            if self.source is None or self.sha256 is not None or self.frame is not None:
                raise AgentError(f"'link {shown(self.target)}' needs only a source entry path")
            if self.overwrite:
                raise AgentError(f"'link {shown(self.target)}' cannot overwrite an entry")
            if not self.source.startswith("/") or self.source == self.target:
                raise AgentError(f"'link {shown(self.target)}' needs another entry as its source")
            try:
                _entry_path(self.source)
            except AgentError:
                raise AgentError(f"invalid source entry {shown(self.source)}") from None

    def describe(self) -> str:
        """One line for the reviewer; every value is shown (escaped and capped)."""
        target = shown(self.target)
        if self.op == "add":
            verb = "replace" if self.overwrite else "add"
            text = f"{verb:<9} {target}  <-  {shown(self.source)}"
            if self.frame is not None and self.attrs.get("source_frames", 1) != 1:
                text += f" [frame {self.frame}]"
        elif self.op == "link":
            text = f"link      {target}  <-  {shown(self.source)}"
            if self.attrs:
                text += f"  {shown(self.attrs, 400)}"
        elif self.op == "remove":
            text = f"remove    {target}"
        else:
            verb = "attrs" if self.op == "set_attrs" else "group"
            text = f"{verb:<9} {target}  {shown(self.attrs, 400)}"
        return text + (f"  ({shown(self.note)})" if self.note else "")

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if k == "op" or v != _DEFAULTS[k]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Operation":
        if not isinstance(data, Mapping):
            raise AgentError("plan operations must be JSON objects")
        unknown = set(data) - {f for f in cls.__dataclass_fields__}
        if unknown:
            raise AgentError(f"unknown operation fields {sorted(unknown)}")
        if not isinstance(data, Mapping):
            raise AgentError("plan operations must be JSON objects")
        try:
            return cls(**dict(data))
        except TypeError as exc:
            raise AgentError(f"invalid operation {dict(data)!r}: {exc}") from None


_DEFAULTS: Dict[str, Any] = {
    "attrs": {},
    "source": None,
    "sha256": None,
    "frame": None,
    "overwrite": False,
    "note": "",
    "target": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Plan:
    """Operations on one dataset, waiting for approval."""

    dataset: str
    operations: List[Operation] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    origin: str = ""
    request: str = ""
    created: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.dataset = str(Path(self.dataset).expanduser().resolve())
        if not isinstance(self.options, dict) or not all(
            isinstance(v, str) for v in self.options.values()
        ):
            raise AgentError("plan options must map option names to strings")
        unknown = set(self.options) - _ENCODE_OPTIONS
        if unknown:
            raise AgentError(f"unknown plan options {sorted(unknown)}")

    def __len__(self) -> int:
        return len(self.operations)

    @property
    def id(self) -> str:
        content = {
            "dataset": self.dataset,
            "options": self.options,
            "operations": [op.to_dict() for op in self.operations],
        }
        text = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def add(self, operation: Operation) -> None:
        """Append ``operation``; creating or removing the same entry twice in a row is an error."""
        kinds = {"add": "add", "link": "add", "remove": "remove"}
        if operation.op in kinds:
            last = [kinds[op.op] for op in self.operations if op.target == operation.target]
            last = [kind for kind in last if kind in ("add", "remove")]
            if last and last[-1] == kinds[operation.op]:
                raise AgentError(f"the plan already creates or removes {shown(operation.target)}")
        self.operations.append(operation)

    def describe(self) -> str:
        counts: Dict[str, int] = {}
        for op in self.operations:
            counts[op.op] = counts.get(op.op, 0) + 1
        summary = ", ".join(f"{n} {k}" for k, n in sorted(counts.items())) or "no operations"
        lines = [f"plan {self.id} for {shown(self.dataset)}: {summary}"]
        if self.options:
            options = ", ".join(f"{k}={shown(v, 40)}" for k, v in sorted(self.options.items()))
            lines.append(f"  options for added structures: {options}")
        if self.request:
            lines.append(f"  request: {shown(self.request, 200)}")
        lines += [f"  {op.describe()}" for op in self.operations]
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": PLAN_FORMAT,
            "id": self.id,
            "dataset": self.dataset,
            "options": self.options,
            "origin": self.origin,
            "request": self.request,
            "created": self.created,
            "operations": [op.to_dict() for op in self.operations],
        }

    def save(self, path: os.PathLike[str] | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"
        atomic_write_text(target, text)
        return target

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Plan":
        if data.get("format") != PLAN_FORMAT:
            raise AgentError(f"not a change plan (format {data.get('format')!r})")
        operations = data.get("operations", [])
        if not isinstance(operations, list) or not isinstance(data.get("dataset"), str):
            raise AgentError("a change plan needs a 'dataset' path and an 'operations' list")
        plan = cls(
            dataset=data["dataset"],
            operations=[Operation.from_dict(op) for op in operations],
            options=data.get("options", {}),
            origin=str(data.get("origin", "")),
            request=str(data.get("request", "")),
            created=str(data.get("created", "")),
        )
        if "id" in data and data["id"] != plan.id:
            raise AgentError(
                f"plan id {data['id']} does not match its content ({plan.id}); it was edited "
                "after it was written: remove the id to accept the edits"
            )
        return plan

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "Plan":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AgentError(f"{path}: not JSON ({exc})") from None
        if not isinstance(data, dict):
            raise AgentError(f"{path}: not a change plan")
        return cls.from_dict(data)


def add_operation(candidate: Candidate, *, overwrite: bool = False, note: str = "") -> Operation:
    return Operation(
        op="add",
        target=candidate.path,
        attrs=candidate.attrs,
        source=str(candidate.source),
        sha256=candidate.sha256,
        frame=candidate.frame,
        overwrite=overwrite,
        note=note or f"{candidate.formula}, {candidate.natoms} atoms",
    )


def plan_from_scan(
    dataset: os.PathLike[str] | str,
    candidates: Sequence[Candidate],
    *,
    update: bool = False,
    options: Optional[Mapping[str, Any]] = None,
    origin: str = "scan",
    request: str = "",
) -> Plan:
    """A plan adding the ``new`` candidates (and replacing ``conflict`` ones if ``update``)."""
    plan = Plan(str(dataset), options=dict(options or {}), origin=origin, request=request)
    for candidate in candidates:
        if candidate.status == "new" or (update and candidate.status == "conflict"):
            plan.add(add_operation(candidate, overwrite=candidate.status == "conflict"))
    return plan


@dataclass
class ApplyReport:
    plan_id: str
    dataset: str
    counts: Dict[str, int]


def _check(plan: Plan, dataset_path: Path) -> List[str]:
    """Problems that would make the plan fail or do something else than approved."""
    problems: List[str] = []
    existing: Optional[Dataset] = Dataset(dataset_path, "r") if dataset_path.exists() else None
    try:
        added = set()
        removed = set()
        for op in plan.operations:
            exists = (op.target in existing) if existing is not None else False
            exists = (exists or op.target in added) and op.target not in removed
            if op.op == "link":
                origin = op.source or ""
                found = existing is not None and origin in existing
                if not (found or origin in added) or origin in removed:
                    problems.append(f"{op.target}: source entry {origin} does not exist")
                if exists:
                    problems.append(f"{op.target}: entry already exists")
                added.add(op.target)
                removed.discard(op.target)
            elif op.op == "add":
                source = Path(op.source or "")
                if not source.is_file():
                    problems.append(f"{op.target}: source {source} is missing")
                elif file_sha256(source) != op.sha256:
                    problems.append(f"{op.target}: source {source} changed since the plan was made")
                if exists and not op.overwrite:
                    problems.append(f"{op.target}: entry already exists")
                added.add(op.target)
                removed.discard(op.target)
            elif op.op in ("set_attrs", "remove"):
                if not exists:
                    problems.append(f"{op.target}: no such entry")
                if op.op == "remove":
                    removed.add(op.target)
                    added.discard(op.target)
    finally:
        if existing is not None:
            existing.close()
    return problems


def apply_plan(plan: Plan, *, dataset: Optional[os.PathLike[str] | str] = None) -> ApplyReport:
    """Execute an approved plan in one transaction (all operations or none).

    ``dataset`` may redirect the plan to another file (e.g. a copy); by default
    the plan's own dataset is used.
    """
    target = Path(dataset).expanduser().resolve() if dataset is not None else Path(plan.dataset)
    problems = _check(plan, target)
    if problems:
        raise AgentError("plan not applied:\n  " + "\n  ".join(problems[:50]))
    counts = {kind: 0 for kind in OPERATIONS}
    stamp = {"plan": plan.id, "registered": _now()}
    with Dataset(target, "a", **plan.options) as data, data.transaction():
        for op in plan.operations:
            try:
                _apply(data, op, stamp)
            except AgentError:
                raise
            except (USIFError, OSError, ValueError, KeyError) as exc:
                text = _describe(exc)
                raise AgentError(f"plan not applied: {shown(op.target)}: {text}") from exc
            counts[op.op] += 1
    return ApplyReport(plan.id, str(target), counts)


def _describe(exc: BaseException) -> str:
    if isinstance(exc, KeyError):
        return f"not found: {exc.args[0] if exc.args else ''}"
    return str(exc) or type(exc).__name__


def _apply(data: Dataset, op: Operation, stamp: Mapping[str, Any]) -> None:
    if op.op == "add":
        source = Path(op.source or "")
        frames = io.read_all(source)
        # The file was hashed in _check; hash it again now that it has been read, so a file
        # replaced in between is not stored under the approved hash.
        if file_sha256(source) != op.sha256:
            raise AgentError(f"plan not applied: {source} changed while the plan was applied")
        index = op.frame if op.frame is not None else len(frames) - 1
        if index >= len(frames):
            raise AgentError(f"plan not applied: {source} has no frame {index}")
        group, _, name = op.target.rpartition("/")
        data.add(frames[index], name, group or "/", {**op.attrs, **stamp}, overwrite=op.overwrite)
    elif op.op == "link":
        origin = op.source or ""
        group, _, name = op.target.rpartition("/")
        attrs = {**data.entry(origin).attrs, **op.attrs, "linked_from": origin, **stamp}
        data.link(origin, name, group or "/", attrs)
    elif op.op == "set_attrs":
        data.set_attrs(op.target, op.attrs)
    elif op.op == "set_group_attrs":
        data.set_group_attrs(op.target, op.attrs)
    else:
        data.remove(op.target)
