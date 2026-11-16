"""pymatgen backend (``pip install usif[pymatgen]``).

* ``Structure`` <-> structure with a cell, ``Molecule`` <-> structure without;
* species -> atomic numbers; ``Species`` oxidation states <-> per-atom
  ``oxidation_state``;
* site properties ``forces``/``charge``/``magmom``/``velocities`` <->
  ``force``/``charge``/``magmom``/``velocity``; others are kept by name;
* ``Molecule.charge``/``spin_multiplicity`` <-> ``charge``/``spin_multiplicity``
  structure properties; other structure properties <-> the ``properties`` dict;
* pymatgen keeps bare numbers, so built-in quantities are exported in the
  default-schema units (eV, eV/Å, GPa, Å/fs, e, μB) and imported with them;
* disordered (partially occupied) sites are rejected.
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
)
from usif.errors import ValidationError
from usif.model.cell import Cell
from usif.model.properties import DEFAULT_SCHEMA, Schema
from usif.model.structure import Structure

__all__ = ["PymatgenBackend"]

OXIDATION_STATE = "oxidation_state"
_IMPORT_NAMES = {
    "forces": "force",
    "force": "force",
    "charge": "charge",
    "charges": "charge",
    "magmom": "magmom",
    "velocities": "velocity",
}
_EXPORT_NAMES = {
    "force": "forces",
    "charge": "charge",
    "magmom": "magmom",
    "velocity": "velocities",
}


class PymatgenBackend:
    name = "pymatgen"

    def accepts(self, obj: Any) -> bool:
        return is_instance_of(obj, "pymatgen", "Structure", "IStructure", "Molecule", "IMolecule")

    def to_structure(self, obj: Any, *, schema: Schema = DEFAULT_SCHEMA) -> Structure:
        if not self.accepts(obj):
            raise ValidationError(f"expected a pymatgen Structure or Molecule, got {type(obj)!r}")
        if not obj.is_ordered:
            raise ValidationError(
                "disordered (partially occupied) structures are not supported; "
                "order the structure first"
            )
        periodic = hasattr(obj, "lattice")
        cell = None
        if periodic:
            pbc = tuple(bool(p) for p in getattr(obj.lattice, "pbc", (True, True, True)))
            cell = Cell(np.array(obj.lattice.matrix, dtype=float), pbc)
        structure = Structure(
            [int(site.specie.Z) for site in obj],
            np.array(obj.cart_coords, dtype=float).reshape(len(obj), 3),
            cell,
            schema=schema,
        )
        oxidation = [getattr(site.specie, "oxi_state", None) for site in obj]
        if any(o is not None for o in oxidation):
            values: Any = (
                np.array(oxidation, dtype=float)
                if all(o is not None for o in oxidation)
                else oxidation
            )
            set_value(structure.arrays, OXIDATION_STATE, values)
        for name, values in (obj.site_properties or {}).items():
            column = [plain(v) for v in values]
            target = _IMPORT_NAMES.get(name, name)
            if target not in structure.arrays:
                set_value(structure.arrays, target, column)
        for key, value in (getattr(obj, "properties", None) or {}).items():
            set_value(structure.properties, str(key), plain(value))
        if not periodic:
            charge = float(getattr(obj, "charge", 0.0) or 0.0)
            spin = getattr(obj, "spin_multiplicity", None)
            if charge != 0.0:
                structure.properties["charge"] = charge
            if spin is not None and int(spin) != 1:
                structure.properties["spin_multiplicity"] = int(spin)
        return structure

    def from_structure(self, structure: Structure) -> Any:
        core = require("pymatgen.core", "pymatgen conversion", "pymatgen")
        arrays = structure.arrays
        oxidation = arrays[OXIDATION_STATE] if OXIDATION_STATE in arrays else None
        species: List[Any] = []
        for i, z in enumerate(structure.numbers.tolist()):
            element = core.Element.from_Z(z)
            state = None if oxidation is None else oxidation[i]
            species.append(core.Species(element.symbol, state) if state is not None else element)
        site_properties: Dict[str, List[Any]] = {}
        for name in arrays:
            if name == OXIDATION_STATE:
                continue
            site_properties[_EXPORT_NAMES.get(name, name)] = list(standard_value(arrays, name))
        props = structure.properties
        cell = structure.cell
        molecule_keys = () if cell is not None else ("charge", "spin_multiplicity")
        extra = {name: standard_value(props, name) for name in props if name not in molecule_keys}
        if cell is not None:
            return core.Structure(
                core.Lattice(cell.matrix, pbc=cell.pbc),
                species,
                structure.positions,
                coords_are_cartesian=True,
                site_properties=site_properties or None,
                properties=extra or None,
            )
        spin = props["spin_multiplicity"] if "spin_multiplicity" in props else None
        return core.Molecule(
            species,
            structure.positions,
            charge=float(standard_value(props, "charge")) if "charge" in props else 0.0,
            spin_multiplicity=int(spin) if spin is not None else None,
            site_properties=site_properties or None,
            properties=extra or None,
        )

    def read(
        self, path: PathLike, format: Optional[str] = None, *, schema: Schema = DEFAULT_SCHEMA
    ) -> List[Structure]:
        core = require("pymatgen.core", "reading files with pymatgen", "pymatgen")
        try:
            obj = core.Structure.from_file(str(path))
        except Exception:
            obj = core.Molecule.from_file(str(path))
        return [self.to_structure(obj, schema=schema)]

    def write(
        self, structures: Sequence[Structure], path: PathLike, format: Optional[str] = None
    ) -> None:
        if len(structures) != 1:
            raise ValidationError("the pymatgen backend writes one structure per file")
        self.from_structure(structures[0]).to(filename=str(path), fmt=format or "")
