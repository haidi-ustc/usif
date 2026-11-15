#!/usr/bin/env python3
"""Use SymmetryPolicy to choose full-atom or symmetry-aware storage (spglib, no backend)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from usif.interop.common import build_structure  # noqa: E402
from usif.symmetry import SymmetryPolicy, apply_symmetry_policy  # noqa: E402


def main() -> None:
    # Conventional rock-salt NaCl cell (8 atoms, space group 225).
    na = [[0, 0, 0], [0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]]
    cl = [[0.5, 0.5, 0.5], [0.5, 0, 0], [0, 0.5, 0], [0, 0, 0.5]]
    source = build_structure(
        [11] * 4 + [17] * 4, na + cl, lattice=np.eye(3) * 5.64, cartesian=False
    )
    analyze = apply_symmetry_policy(source, SymmetryPolicy(mode="analyze"))
    full = apply_symmetry_policy(source, SymmetryPolicy(mode="none"))

    print(f"Analyze policy mode: {analyze.storage_mode.name}")
    print(f"None policy mode: {full.storage_mode.name}")
    print(f"Formula: {analyze.formula}")
    if analyze.wyckoff_sites:
        print(f"Space group: {analyze.spacegroup}, representatives: {len(analyze.wyckoff_sites)}")


if __name__ == "__main__":
    main()
