"""matsimpy backend (``pip install usif[matsimpy]``).

* ``Crystal`` <-> structure with a cell (``lattice.matrix`` rows are lattice
  vectors), ``Molecule`` <-> structure without;
* per-site dict keys ``force(s)``/``charge``/``magmom``/``velocit(y|ies)`` <->
  ``force``/``charge``/``magmom``/``velocity``; other keys are kept by name;
* ``metadata`` <-> ``Structure.properties``; ``stress`` is a 3x3 tensor in
  eV/Å³ there (matsimpy's calculator convention, positive is tensile) and in
  GPa Voigt order here;
* built-in quantities are exported in matsimpy's units (eV, eV/Å, Å/fs, e,
  μB), converted from their stored unit.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from usif.backends.base import (
    PathLike,
    is_instance_of,
    plain,
    require,
    set_value,
    standard_value,
    value_in,
)
from usif.elements import atomic_number
from usif.errors import ValidationError
from usif.model.cell import Cell
from usif.model.properties import DEFAULT_SCHEMA, Schema, voigt_to_tensor
from usif.model.structure import Structure
from usif.units import EV_PER_ANG3_IN_GPA

__all__ = ["MatsimpyBackend"]

_SITE_KEYS = {
    "force": "force",
    "forces": "force",
    "charge": "charge",
    "magmom": "magmom",
    "velocity": "velocity",
    "velocities": "velocity",
}


def _number(specie: Any) -> int:
    if isinstance(specie, (int, np.integer)):
        return int(specie)
    return atomic_number(str(getattr(specie, "symbol", specie)))


class MatsimpyBackend:
    name = "matsimpy"

    def accepts(self, obj: Any) -> bool:
        return is_instance_of(obj, "matsimpy", "Crystal", "Molecule")

    def to_structure(self, obj: Any, *, schema: Schema = DEFAULT_SCHEMA) -> Structure:
        if not self.accepts(obj):
            raise ValidationError(f"expected a matsimpy Crystal or Molecule, got {type(obj)!r}")
        numbers = [_number(s) for s in obj.species]
        cell = None
        if is_instance_of(obj, "matsimpy", "Crystal"):
            pbc = tuple(bool(p) for p in (getattr(obj, "pbc", None) or (True, True, True)))
            cell = Cell(np.array(obj.lattice.matrix, dtype=float), pbc)
        structure = Structure(
            numbers,
            np.array(obj.positions, dtype=float).reshape(len(numbers), 3),
            cell,
            schema=schema,
        )
        columns: Dict[str, List[Any]] = {}
        for index, props in enumerate(obj.site_properties or ()):
            for key, value in (props or {}).items():
                target = _SITE_KEYS.get(key, key)
                columns.setdefault(target, [None] * len(numbers))[index] = plain(value)
        for name, column in columns.items():
            set_value(structure.arrays, name, column)
        for key, value in dict(getattr(obj, "metadata", None) or {}).items():
            if key == "stress":
                try:
                    stress = np.asarray(value, dtype=float) * EV_PER_ANG3_IN_GPA
                except (TypeError, ValueError):
                    stress = value
                set_value(structure.properties, "stress", stress)
            else:
                set_value(structure.properties, str(key), plain(value))
        return structure

    def from_structure(self, structure: Structure) -> Any:
        matsimpy = require("matsimpy", "matsimpy conversion", "matsimpy")
        arrays = structure.arrays
        names = list(arrays)
        columns = {name: standard_value(arrays, name) for name in names}
        site_properties = [
            {name: columns[name][i] for name in names if columns[name][i] is not None}
            for i in range(structure.natoms)
        ]
        metadata: Dict[str, Any] = {}
        props = structure.properties
        for name in props:
            if name == "stress":
                tensor = voigt_to_tensor(value_in(props, "stress", "eV/Å^3"))
                metadata[name] = tensor.tolist()
            else:
                metadata[name] = standard_value(props, name)
        symbols = structure.symbols
        sites = site_properties if any(site_properties) else None
        cell = structure.cell
        if cell is not None:
            return matsimpy.Crystal(
                symbols,
                structure.positions.tolist(),
                matsimpy.Lattice(cell.matrix),
                pbc=list(cell.pbc),
                coords_are_cartesian=True,
                site_properties=sites,
                metadata=metadata or None,
            )
        return matsimpy.Molecule(
            symbols, structure.positions.tolist(), site_properties=sites, metadata=metadata or None
        )

    def read(
        self, path: PathLike, format: Optional[str] = None, *, schema: Schema = DEFAULT_SCHEMA
    ) -> List[Structure]:
        io = require("matsimpy.io", "reading files with matsimpy", "matsimpy")
        result = io.read(str(path), format=format)
        frames = result if isinstance(result, list) else [result]
        return [self.to_structure(frame, schema=schema) for frame in frames]

    def write(
        self, structures: Sequence[Structure], path: PathLike, format: Optional[str] = None
    ) -> None:
        if len(structures) != 1:
            raise ValidationError("the matsimpy backend writes one structure per file")
        io = require("matsimpy.io", "writing files with matsimpy", "matsimpy")
        io.write(self.from_structure(structures[0]), str(path), format=format)
