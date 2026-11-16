"""Architecture rules from PLAN.md section 3, checked on the source tree.

Every ``usif`` import is collected with ``ast`` (including imports inside
functions), so lazy imports are held to the same layering as module-level ones.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, Iterator, Set, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "usif"

BASICS = {"version", "errors", "elements", "formula", "units", "fileio"}
#: layer -> layers it may import (besides itself and the basics)
ALLOWED: Dict[str, Set[str]] = {
    "basics": set(),
    "model": set(),
    "symmetry": {"model"},
    "codec": {"model", "symmetry"},
    "upgrade": {"model", "symmetry", "codec.wire"},
    "dataset": {"model", "codec", "upgrade"},
    "backends": {"model"},
    "io": {"model", "codec", "upgrade", "backends"},
    "agent": {"model", "dataset", "io"},
    "cli": {"model", "codec", "upgrade", "dataset", "backends", "io", "agent"},
    "__init__": {"model", "codec", "io", "dataset"},
}
OPTIONAL_LIBRARIES = {"ase", "pymatgen", "matsimpy", "zstandard", "mp_api", "monty"}
BANNED_TERMS = re.compile(
    r"legacy|historical|backward-compatible|compatibility facade|transitional|"
    r"old fallback|older payload|alias for add|\bP[123] ",
    re.IGNORECASE,
)


def modules() -> Iterator[Tuple[Path, str]]:
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = path.relative_to(PACKAGE).with_suffix("").parts
        head = parts[0]
        if head in BASICS:
            layer = "basics"
        else:
            layer = head
        yield path, layer


def usif_imports(tree: ast.AST) -> Iterator[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "usif" or alias.name.startswith("usif."):
                    yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "usif":
                for alias in node.names:
                    yield f"usif.{alias.name}"
            elif node.module.startswith("usif."):
                yield node.module


def target_layer(module: str) -> str:
    parts = module.split(".")[1:]
    if not parts:
        return "__init__"
    if parts[0] in BASICS:
        return "basics"
    return parts[0]


def allowed(layer: str, module: str) -> bool:
    target = target_layer(module)
    if target in ("basics", layer):
        return True
    rules = ALLOWED[layer]
    if target in rules:
        return True
    dotted = ".".join(module.split(".")[1:3])
    return dotted in rules


def test_every_module_belongs_to_a_known_layer():
    unknown = {layer for _, layer in modules()} - set(ALLOWED)
    assert not unknown, f"add these packages to the layer table: {unknown}"


@pytest.mark.parametrize("path, layer", list(modules()), ids=lambda v: str(v))
def test_imports_follow_the_layer_table(path, layer):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations = [m for m in usif_imports(tree) if not allowed(layer, m)]
    assert not violations, f"{path.relative_to(ROOT)} ({layer}) imports {violations}"


@pytest.mark.parametrize("path, layer", list(modules()), ids=lambda v: str(v))
def test_optional_libraries_are_imported_lazily(path, layer):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:  # module level only
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        for name in names:
            assert (
                name.split(".")[0] not in OPTIONAL_LIBRARIES
            ), f"{path.relative_to(ROOT)} imports optional {name} at module level"


def test_no_relative_imports():
    for path, _ in modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        relative = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level]
        assert not relative, f"{path.relative_to(ROOT)} uses relative imports"


def test_applications_live_outside_the_package():
    """Benchmarks and the Materials Project tooling are scripts, not library modules."""
    assert not (PACKAGE / "integrations").exists()
    assert not (PACKAGE / "benchmarks.py").exists()
    assert (ROOT / "scripts" / "benchmark.py").exists()
    assert (ROOT / "scripts" / "materials_project" / "__main__.py").exists()


def test_source_has_no_migration_stage_wording():
    offenders = []
    for path, _ in modules():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if BANNED_TERMS.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_frozen_symmetry_tables_are_unchanged():
    """The format-5 tables define how existing files decode; they must never change."""
    import hashlib

    from usif.symmetry.tables import FORMAT5_POINT_GROUP_ROTATIONS, FORMAT5_SPACEGROUP_HALL

    content = repr(
        (sorted(FORMAT5_SPACEGROUP_HALL.items()), sorted(FORMAT5_POINT_GROUP_ROTATIONS.items()))
    )
    assert (
        hashlib.sha256(content.encode()).hexdigest()
        == "b98ed93282e4003cb9b402f196a5786513cc24ab23571edb817cbcb98af742de"
    )
