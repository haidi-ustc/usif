"""The agent's tools: read-only access to one dataset and the project files, plus proposals.

:class:`Toolbox` is everything the model can do. Reading tools open the
dataset in ``"r"`` mode for each call; files are read only below the allowed
roots. ``propose_*`` tools only append operations to :attr:`Toolbox.plan`;
nothing here writes to the dataset (see :mod:`usif.agent.plan`).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import numpy as np

from usif import io
from usif.agent.discover import ScanResult, scan
from usif.agent.llm import tool_spec
from usif.agent.plan import Operation, Plan, add_operation
from usif.dataset import Dataset, Q
from usif.errors import AgentError, USIFError, ValidationError

__all__ = ["Toolbox"]

MAX_RESULT_CHARS = 16000
MAX_LIMIT = 50
TEXT_SCAN_LIMIT = 20000
_OPS = {
    "<": "__lt__",
    "<=": "__le__",
    ">": "__gt__",
    ">=": "__ge__",
    "==": "__eq__",
    "!=": "__ne__",
}

_ATTRS = {"type": "object", "description": 'JSON attributes, e.g. {"method": "PBE"}'}
_REASON = {"type": "string", "description": "Why this change is proposed (shown to the reviewer)."}


def _trim(value: Any, limit: int = 300) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "..."
    if isinstance(value, dict):
        return {k: _trim(v, limit) for k, v in value.items()}
    return value


class Toolbox:
    """Tools over ``dataset`` and the directories in ``roots``."""

    def __init__(
        self,
        dataset: os.PathLike[str] | str,
        *,
        roots: Sequence[os.PathLike[str] | str] = (),
        plan: Optional[Plan] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.dataset = Path(dataset).expanduser().resolve()
        self.roots = [Path(r).expanduser().resolve() for r in roots]
        self.plan = plan or Plan(str(self.dataset), options=dict(options or {}))
        self.scans: List[ScanResult] = []
        self._tools: Dict[str, Callable[..., Any]] = {
            "dataset_overview": self.dataset_overview,
            "search_entries": self.search_entries,
            "get_entry": self.get_entry,
            "inspect_file": self.inspect_file,
            "scan_directory": self.scan_directory,
            "propose_import": self.propose_import,
            "propose_entry_attrs": self.propose_entry_attrs,
            "propose_group_attrs": self.propose_group_attrs,
            "propose_remove": self.propose_remove,
            "show_plan": self.show_plan,
            "discard_plan": self.discard_plan,
        }

    # -- dispatch -------------------------------------------------------------

    def call(self, name: str, arguments: Mapping[str, Any]) -> str:
        """Run a tool and return its JSON result; errors are results, not exceptions."""
        function = self._tools.get(name)
        if function is None:
            result: Any = {"error": f"unknown tool {name!r}"}
        else:
            operations = list(self.plan.operations)
            try:
                result = function(**dict(arguments))
            except Exception as exc:  # any failure is reported to the model, never raised
                self.plan.operations[:] = operations  # a failed proposal adds nothing
                if isinstance(exc, KeyError):
                    result = {"error": f"not found: {exc.args[0] if exc.args else ''}"}
                elif isinstance(exc, (USIFError, OSError, ValueError)):
                    result = {"error": str(exc) or type(exc).__name__}
                else:
                    result = {"error": f"bad arguments for {name}: {type(exc).__name__}: {exc}"}
        text = json.dumps(result, ensure_ascii=False, default=str)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + '..." [truncated: narrow the request]'
        return text

    def _open(self) -> Dataset:
        if not self.dataset.exists():
            raise AgentError(
                f"the dataset {self.dataset} does not exist yet (it is created when a plan is applied)"
            )
        return Dataset(self.dataset, "r")

    def _allowed(self, path: str) -> Path:
        resolved = Path(path).expanduser().resolve()
        if not any(resolved == root or root in resolved.parents for root in self.roots):
            allowed = ", ".join(map(str, self.roots)) or "none"
            raise AgentError(f"{resolved} is outside the allowed directories ({allowed})")
        return resolved

    # -- reading --------------------------------------------------------------

    def dataset_overview(self) -> Dict[str, Any]:
        """Size, groups (with their attributes) and allowed directories."""
        if not self.dataset.exists():
            return {
                "dataset": str(self.dataset),
                "exists": False,
                "allowed_dirs": list(map(str, self.roots)),
            }
        with self._open() as data:
            groups = data.groups()
            return {
                "dataset": str(self.dataset),
                "exists": True,
                **data.stats(),
                "groups": {g: _trim(data.group_attrs(g)) for g in groups[:200]},
                "allowed_dirs": list(map(str, self.roots)),
            }

    def search_entries(
        self,
        group: Optional[str] = None,
        formula: Optional[str] = None,
        chemsys: Optional[str] = None,
        elements: Optional[List[str]] = None,
        exclude_elements: Optional[List[str]] = None,
        natoms_min: Optional[int] = None,
        natoms_max: Optional[int] = None,
        properties: Optional[List[Dict[str, Any]]] = None,
        attrs: Optional[Dict[str, Any]] = None,
        text: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        where = Q.all()
        if group:
            where &= Q.group(group)
        if formula:
            where &= Q.formula(formula)
        if chemsys:
            where &= Q.chemsys(chemsys)
        if elements:
            where &= Q.elements(*elements)
        for symbol in exclude_elements or []:
            where &= ~Q.elements(symbol)
        if natoms_min is not None or natoms_max is not None:
            where &= Q.natoms(min=natoms_min, max=natoms_max)
        for condition in properties or []:
            op = _OPS.get(str(condition.get("op")))
            if op is None or "name" not in condition or "value" not in condition:
                raise ValidationError(
                    f"property conditions are {{name, op, value}} with op in {sorted(_OPS)}"
                )
            where &= getattr(Q.prop(str(condition["name"])), op)(condition["value"])
        for key, value in (attrs or {}).items():
            where &= Q.attr(key) == value
        limit = max(1, min(int(limit), MAX_LIMIT))
        needle = text.lower() if text else None
        rows = []
        with self._open() as data:
            total = data.count(where)
            scan_limit = TEXT_SCAN_LIMIT if needle else limit
            for entry in data.query(where, limit=scan_limit, load=True):
                if (
                    needle
                    and needle
                    not in (
                        (entry.path or "") + json.dumps(entry.attrs, ensure_ascii=False)
                    ).lower()
                ):
                    continue
                structure = entry.structure
                rows.append(
                    {
                        "path": entry.path or f"{entry.group} <unnamed {entry.record_hash[:12]}>",
                        "formula": structure.reduced_formula,
                        "natoms": structure.natoms,
                        "properties": _scalars(structure),
                        "attrs": _trim({k: v for k, v in entry.attrs.items() if k != "incar"}, 200),
                    }
                )
                if len(rows) >= limit:
                    break
        return {"matching_records_conditions": total, "returned": len(rows), "entries": rows}

    def get_entry(self, path: str) -> Dict[str, Any]:
        with self._open() as data:
            entry = data.entry(path)
            structure = entry.structure
        result: Dict[str, Any] = {
            "path": entry.path,
            "record_hash": entry.record_hash,
            "formula": structure.formula,
            "reduced_formula": structure.reduced_formula,
            "natoms": structure.natoms,
            "properties": {
                name: {
                    "value": _jsonable(structure.properties[name]),
                    "unit": structure.properties.unit(name),
                }
                for name in structure.properties
            },
            "arrays": {name: structure.arrays.unit(name) for name in structure.arrays},
            "attrs": _trim(entry.attrs, 2000),
        }
        if structure.cell is not None:
            cell = structure.cell
            result["cell"] = {
                "lengths": np.round(cell.lengths, 5).tolist(),
                "angles": np.round(cell.angles, 3).tolist(),
                "volume": round(float(cell.volume), 4),
            }
        return result

    def inspect_file(self, path: str) -> Dict[str, Any]:
        source = self._allowed(path)
        frames = io.read_all(source)
        last = frames[-1]
        return {
            "path": str(source),
            "frames": len(frames),
            "formula": last.reduced_formula,
            "natoms": last.natoms,
            "properties": _scalars(last),
            "arrays": list(last.arrays),
        }

    def scan_directory(self, path: str, group: str, all_frames: bool = False) -> Dict[str, Any]:
        root = self._allowed(path)
        result = scan(root, group=group, dataset=self.dataset, all_frames=all_frames)
        self.scans.append(result)
        scan_id = len(self.scans) - 1
        listed = [{"index": i, **c.summary()} for i, c in enumerate(result.candidates)][:100]
        return {
            "scan_id": scan_id,
            "root": str(root),
            "found": len(result.candidates),
            "new": len(result.new),
            "candidates": listed,
            "skipped": [{"path": p, "reason": r} for p, r in result.skipped[:30]],
        }

    # -- proposals ------------------------------------------------------------

    def _proposed(self, operations: List[Operation]) -> Dict[str, Any]:
        return {
            "proposed": [op.describe() for op in operations],
            "plan_operations": len(self.plan),
            "note": "Recorded in the change plan. Nothing was written: the user reviews and approves the plan.",
        }

    def propose_import(
        self,
        scan_id: int,
        indices: Optional[List[int]] = None,
        replace_conflicts: bool = False,
        reason: str = "",
    ) -> Dict[str, Any]:
        try:
            result = self.scans[int(scan_id)]
        except (IndexError, ValueError):
            raise AgentError(f"no scan {scan_id}; call scan_directory first") from None
        if indices is None:
            chosen = result.candidates
        else:
            count = len(result.candidates)
            bad = [i for i in indices if not isinstance(i, int) or not 0 <= i < count]
            if bad:
                raise AgentError(f"indices must be 0..{count - 1}, got {bad}")
            chosen = [result.candidates[i] for i in indices]
        added = []
        for candidate in chosen:
            if candidate.status in ("registered", "duplicate"):
                continue
            if candidate.status == "conflict" and not replace_conflicts:
                continue
            operation = add_operation(
                candidate, overwrite=candidate.status == "conflict", note=reason
            )
            self.plan.add(operation)
            added.append(operation)
        return self._proposed(added)

    def propose_entry_attrs(
        self, path: str, attrs: Dict[str, Any], reason: str = ""
    ) -> Dict[str, Any]:
        with self._open() as data:
            data.entry(path)
        self.plan.add(Operation("set_attrs", path, attrs, note=reason))
        return self._proposed(self.plan.operations[-1:])

    def propose_group_attrs(
        self, group: str, attrs: Dict[str, Any], reason: str = ""
    ) -> Dict[str, Any]:
        self.plan.add(Operation("set_group_attrs", group, attrs, note=reason))
        return self._proposed(self.plan.operations[-1:])

    def propose_remove(self, path: str, reason: str = "") -> Dict[str, Any]:
        with self._open() as data:
            data.entry(path)
        self.plan.add(Operation("remove", path, note=reason))
        return self._proposed(self.plan.operations[-1:])

    def show_plan(self) -> Dict[str, Any]:
        return {"plan": self.plan.describe()}

    def discard_plan(self) -> Dict[str, Any]:
        self.plan.operations.clear()
        return {"plan_operations": 0}

    # -- schemas --------------------------------------------------------------

    @staticmethod
    def specs() -> List[Dict[str, Any]]:
        string = {"type": "string"}
        strings = {"type": "array", "items": {"type": "string"}}
        return [
            tool_spec(
                "dataset_overview",
                "Entry/record counts, groups with their attributes, and the directories you may scan.",
                {},
                [],
            ),
            tool_spec(
                "search_entries",
                "Find dataset entries. All filters are optional and combined with AND. "
                "Returns formula, atom count, numeric properties and attributes of each entry.",
                {
                    "group": {"type": "string", "description": "Group path; includes subgroups."},
                    "formula": {"type": "string", "description": "Reduced formula, e.g. Fe2O3."},
                    "chemsys": {"type": "string", "description": "Exact element set, e.g. Fe-O."},
                    "elements": {**strings, "description": "Must contain all of these."},
                    "exclude_elements": {**strings, "description": "Must contain none of these."},
                    "natoms_min": {"type": "integer"},
                    "natoms_max": {"type": "integer"},
                    "properties": {
                        "type": "array",
                        "description": "Numeric property conditions, e.g. energy (eV) < -10, band_gap (eV) > 1.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": string,
                                "op": {"type": "string", "enum": sorted(_OPS)},
                                "value": {"type": "number"},
                            },
                            "required": ["name", "op", "value"],
                        },
                    },
                    "attrs": {
                        **_ATTRS,
                        "description": 'Exact matches of top-level attributes, e.g. {"code": "vasp"}.',
                    },
                    "text": {
                        "type": "string",
                        "description": "Case-insensitive substring of the entry path or attributes (source path, notes, INCAR).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": f"At most {MAX_LIMIT}; default 20.",
                    },
                },
                [],
            ),
            tool_spec(
                "get_entry",
                "Full details of one entry: cell, properties with units, attributes.",
                {"path": {"type": "string", "description": "/group/name"}},
                ["path"],
            ),
            tool_spec(
                "inspect_file",
                "Read a structure file (allowed directories only) without storing it.",
                {"path": string},
                ["path"],
            ),
            tool_spec(
                "scan_directory",
                "Find calculations (VASP directories) and structure files under a directory (allowed directories only). "
                "Each candidate gets a proposed entry path and a status: new, registered (already in the dataset) or conflict "
                "(path taken by other content). Read-only.",
                {
                    "path": string,
                    "group": {
                        "type": "string",
                        "description": "Group the entries go below, e.g. /projects/perovskites; "
                        "subdirectories become subgroups. To change it, scan again.",
                    },
                    "all_frames": {
                        "type": "boolean",
                        "description": "One entry per frame instead of the final structure.",
                    },
                },
                ["path", "group"],
            ),
            tool_spec(
                "propose_import",
                "Propose adding scanned candidates to the dataset (default: every new candidate of the scan).",
                {
                    "scan_id": {"type": "integer"},
                    "indices": {"type": "array", "items": {"type": "integer"}},
                    "replace_conflicts": {"type": "boolean"},
                    "reason": _REASON,
                },
                ["scan_id"],
            ),
            tool_spec(
                "propose_entry_attrs",
                "Propose merging attributes into an entry (e.g. a description, tags, method).",
                {"path": string, "attrs": _ATTRS, "reason": _REASON},
                ["path", "attrs"],
            ),
            tool_spec(
                "propose_group_attrs",
                "Propose merging attributes into a group (e.g. its description).",
                {"group": string, "attrs": _ATTRS, "reason": _REASON},
                ["group", "attrs"],
            ),
            tool_spec(
                "propose_remove",
                "Propose removing an entry.",
                {"path": string, "reason": _REASON},
                ["path", "reason"],
            ),
            tool_spec("show_plan", "The change plan proposed so far.", {}, []),
            tool_spec("discard_plan", "Drop every proposed change.", {}, []),
        ]


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return np.round(value, 6).tolist() if value.size <= 64 else f"array{value.shape}"
    if isinstance(value, np.generic):
        return value.item()
    return value


def _scalars(structure: Any) -> Dict[str, Any]:
    values = {}
    for name in structure.properties:
        raw = structure.properties.raw(name)
        if getattr(raw, "ndim", None) == 0 and raw.dtype.kind in "fiu":
            values[name] = round(float(raw), 6)
        elif getattr(raw, "ndim", None) == 0 and raw.dtype.kind in "OU":
            values[name] = _trim(str(structure.properties[name]), 100)
    return values
