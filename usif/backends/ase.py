"""ASE backend (``pip install usif[ase]``).

* ``numbers``/``positions``/``cell``/``pbc``; a degenerate cell means no cell;
* calculator results (energy, free energy, forces, stress, dipole, charges,
  magnetic moments) map to ``energy``/``free_energy``/``force``/``stress``/
  ``dipole``/``charge``/``magmom``; without a calculator, non-zero
  ``initial_charges``/``initial_magmoms`` are used;
* units: ASE works in eV, Å, e and μB, with stress in eV/Å³ and its own time
  unit. Values are converted with ``ase.units`` on the way in (stress to GPa,
  velocity to Å/fs) and from their stored unit on the way out; a stored unit
  that cannot be converted raises ``ValidationError``. Both use the same
  stress sign (positive is tensile);
* other per-atom arrays (``tags``, ...) <-> ``Structure.arrays``;
  JSON-compatible ``info`` entries <-> ``Structure.properties``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from usif.backends.base import PathLike, is_instance_of, plain, require, set_value, value_in
from usif.model.cell import Cell
from usif.model.properties import DEFAULT_SCHEMA, JSON, Schema, voigt_to_tensor
from usif.model.structure import Structure

__all__ = ["AseBackend"]

_ARRAYS_HANDLED = {
    "numbers",
    "positions",
    "momenta",
    "masses",
    "initial_magmoms",
    "initial_charges",
}
_PROPERTIES_HANDLED = {"energy", "free_energy", "stress", "dipole"}
_ATOM_RESULTS = {"force", "charge", "magmom", "velocity"}


def _result(atoms: Any, getter: str, **kwargs: Any) -> Optional[Any]:
    if atoms.calc is None:
        return None
    try:
        return getattr(atoms, getter)(**kwargs)
    except Exception:  # the calculator does not provide this property
        return None


def _nonzero(values: Any) -> Optional[np.ndarray]:
    array = np.asarray(values, dtype=float)
    return array if array.size and np.any(array != 0) else None


class AseBackend:
    name = "ase"

    def accepts(self, obj: Any) -> bool:
        return is_instance_of(obj, "ase", "Atoms")

    def to_structure(self, obj: Any, *, schema: Schema = DEFAULT_SCHEMA) -> Structure:
        units = require("ase.units", "ASE conversion", "ase")
        matrix = np.array(obj.cell.array, dtype=float)
        cell = (
            Cell(matrix, tuple(bool(p) for p in obj.pbc))
            if abs(np.linalg.det(matrix)) > 1e-8
            else None
        )
        structure = Structure(obj.numbers, obj.positions, cell, schema=schema)
        arrays = structure.arrays

        forces = _result(obj, "get_forces")
        if forces is not None:
            set_value(arrays, "force", forces)
        charges = _result(obj, "get_charges")
        if charges is None and obj.has("initial_charges"):
            charges = _nonzero(obj.get_initial_charges())
        if charges is not None:
            set_value(arrays, "charge", charges)
        magmoms = _result(obj, "get_magnetic_moments")
        if magmoms is None and obj.has("initial_magmoms"):
            magmoms = _nonzero(obj.get_initial_magnetic_moments())
        if magmoms is not None:
            set_value(arrays, "magmom", magmoms)
        if obj.has("momenta"):
            velocities = _nonzero(obj.get_velocities())
            if velocities is not None:
                arrays.set("velocity", velocities * units.fs, unit="Å/fs")
        for name, values in obj.arrays.items():
            if name not in _ARRAYS_HANDLED and name not in arrays:
                set_value(arrays, name, values)

        props = structure.properties
        energy = _result(obj, "get_potential_energy")
        if energy is not None:
            props.set("energy", float(energy), unit="eV")
        if obj.calc is not None and "free_energy" in getattr(obj.calc, "results", {}):
            props.set("free_energy", float(obj.calc.results["free_energy"]), unit="eV")
        stress = _result(obj, "get_stress", voigt=False)
        if stress is not None:
            props.set("stress", np.asarray(stress, dtype=float) / units.GPa, unit="GPa")
        dipole = _result(obj, "get_dipole_moment")
        if dipole is not None:
            props.set("dipole", np.asarray(dipole, dtype=float), unit="e·Å")
        for key, value in obj.info.items():
            if key not in structure.properties:
                set_value(structure.properties, str(key), plain(value))
        return structure

    def from_structure(self, structure: Structure) -> Any:
        ase = require("ase", "ASE conversion", "ase")
        units = require("ase.units", "ASE conversion", "ase")
        singlepoint = require("ase.calculators.singlepoint", "ASE conversion", "ase")
        cell = structure.cell
        atoms = ase.Atoms(
            numbers=structure.numbers,
            positions=structure.positions,
            cell=None if cell is None else cell.matrix,
            pbc=False if cell is None else cell.pbc,
        )
        arrays = structure.arrays
        if "charge" in arrays:
            atoms.set_initial_charges(value_in(arrays, "charge", "e"))
        if "magmom" in arrays:
            atoms.set_initial_magnetic_moments(value_in(arrays, "magmom", "μB"))
        if "velocity" in arrays:
            atoms.set_velocities(value_in(arrays, "velocity", "Å/fs") / units.fs)
        for name in arrays:
            if name in _ATOM_RESULTS or name in _ARRAYS_HANDLED:
                continue
            if arrays.dtype(name) == JSON:
                continue  # ASE arrays are numeric
            atoms.set_array(name, np.array(arrays[name]))
        results: Dict[str, Any] = {}
        props = structure.properties
        for name in ("energy", "free_energy"):
            if name in props:
                results[name] = value_in(props, name, "eV")
        if "force" in arrays:
            results["forces"] = value_in(arrays, "force", "eV/Å")
        if "stress" in props:
            results["stress"] = voigt_to_tensor(value_in(props, "stress", "GPa")) * units.GPa
        if "dipole" in props:
            results["dipole"] = value_in(props, "dipole", "e·Å")
        for name in props:
            if name not in _PROPERTIES_HANDLED:
                value = props[name]
                atoms.info[name] = value.tolist() if isinstance(value, np.ndarray) else value
        if results:
            atoms.calc = singlepoint.SinglePointCalculator(atoms, **results)
        return atoms

    def read(
        self, path: PathLike, format: Optional[str] = None, *, schema: Schema = DEFAULT_SCHEMA
    ) -> List[Structure]:
        io = require("ase.io", "reading files with ASE", "ase")
        frames = io.read(str(path), index=":", format=format)
        return [self.to_structure(atoms, schema=schema) for atoms in frames]

    def write(
        self, structures: Sequence[Structure], path: PathLike, format: Optional[str] = None
    ) -> None:
        io = require("ase.io", "writing files with ASE", "ase")
        frames = [self.from_structure(s) for s in structures]
        io.write(str(path), frames if len(frames) != 1 else frames[0], format=format)
