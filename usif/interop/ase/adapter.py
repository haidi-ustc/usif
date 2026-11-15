"""Optional ASE adapter (``pip install usif[ase]``). Does not need pymatgen.

Mapping:

* ``numbers``/``positions``/``cell``/``pbc``; an atoms object with a
  non-degenerate cell is a crystal, otherwise a molecule
* calculator results (energy, forces, stress, charges, magnetic moments) are
  used when present, otherwise ``initial_charges``/``initial_magmoms``
* stress is converted from eV/Å³ (ASE) to GPa (USIF); velocities from ASE
  units to Å/fs
* other per-atom arrays (e.g. ``tags``) become per-atom custom values and
  JSON-compatible ``info`` entries become structure custom values
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from usif.interop.common.arrays import (
    AtomsData,
    stress_to_voigt,
    structure_to_arrays,
    voigt_to_tensor,
)
from usif.interop.common.importing import import_atoms
from usif.interop.common.type_guards import is_ase_atoms
from usif.properties.values import normalize_json_value
from usif.structures.structure import USIFStructure
from usif.symmetry.policies import SymmetryPolicy

logger = logging.getLogger(__name__)

#: 1 eV/Å³ in GPa.
EV_PER_ANG3_TO_GPA = 160.21766208
#: Arrays handled explicitly (everything else becomes per-atom custom data).
_KNOWN_ARRAYS = {"numbers", "positions", "momenta", "masses", "initial_magmoms", "initial_charges"}


def _require_ase():
    try:
        import ase  # noqa: F401
        from ase import units
        from ase.calculators.singlepoint import SinglePointCalculator
    except ImportError as exc:
        raise ImportError("ASE conversion requires ASE: pip install usif[ase]") from exc
    return units, SinglePointCalculator


def _calc_result(atoms: Any, getter: str, **kwargs: Any) -> Optional[Any]:
    if atoms.calc is None:
        return None
    try:
        return getattr(atoms, getter)(**kwargs)
    except Exception:  # property not available from this calculator
        return None


def _nonzero_or_none(values: Any) -> Optional[List[Any]]:
    array = np.asarray(values)
    return array.tolist() if array.size and np.any(array != 0) else None


def _atoms_from_ase(atoms: Any) -> AtomsData:
    units, _ = _require_ase()
    count = len(atoms)
    cell = np.array(atoms.cell.array if hasattr(atoms.cell, "array") else atoms.cell, dtype=float)
    lattice = cell if cell.shape == (3, 3) and abs(np.linalg.det(cell)) > 1e-8 else None

    atomic: Dict[str, List[Any]] = {}
    forces = _calc_result(atoms, "get_forces")
    if forces is not None:
        atomic["force"] = np.asarray(forces).tolist()
    charges = _calc_result(atoms, "get_charges")
    if charges is None and atoms.has("initial_charges"):
        charges = _nonzero_or_none(atoms.get_initial_charges())
    if charges is not None:
        atomic["charge"] = np.asarray(charges).tolist()
    magmoms = _calc_result(atoms, "get_magnetic_moments")
    if magmoms is None and atoms.has("initial_magmoms"):
        magmoms = _nonzero_or_none(atoms.get_initial_magnetic_moments())
    if magmoms is not None:
        if np.ndim(magmoms) == 1:
            atomic["magmom"] = np.asarray(magmoms).tolist()
    if atoms.has("momenta"):
        velocities = _nonzero_or_none(atoms.get_velocities())
        if velocities is not None:
            atomic["velocity"] = (np.asarray(velocities) * units.fs).tolist()

    site_custom: List[Dict[str, Any]] = [{} for _ in range(count)]
    for name, values in atoms.arrays.items():
        if name in _KNOWN_ARRAYS or name == "forces":
            continue
        for extra, value in zip(site_custom, np.asarray(values).tolist()):
            extra[name] = value

    custom: Dict[str, Any] = {}
    for key, value in atoms.info.items():
        try:
            custom[str(key)] = normalize_json_value(value)
        except (TypeError, ValueError):
            logger.debug("Skipping non-JSON ASE info entry %r", key)

    energy = _calc_result(atoms, "get_potential_energy")
    stress = _calc_result(atoms, "get_stress", voigt=False)
    return AtomsData(
        numbers=[int(z) for z in atoms.numbers],
        positions=np.array(atoms.positions, dtype=float),
        lattice=lattice,
        pbc=tuple(bool(p) for p in atoms.pbc),  # type: ignore[arg-type]
        atomic=atomic,
        site_custom=site_custom,
        energy=float(energy) if energy is not None else None,
        stress=(
            None
            if stress is None
            else stress_to_voigt(np.asarray(stress, dtype=float) * EV_PER_ANG3_TO_GPA)
        ),
        custom=custom,
    )


class ASEImporter:
    """Convert ASE ``Atoms`` to USIF."""

    @staticmethod
    def from_ase(
        ase_atoms: Any,
        /,
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        force_symmetric: bool = False,
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        symmetry_policy: Optional[SymmetryPolicy] = None,
        **kwargs: Any,
    ) -> USIFStructure:
        """Convert an ``ase.Atoms`` object.

        An explicit ``stress`` argument is taken to be in GPa (USIF units);
        stress read from the calculator is converted from eV/Å³.
        """
        if not is_ase_atoms(ase_atoms):
            raise TypeError(
                "Expected ase.Atoms, got "
                f"{type(ase_atoms).__module__}.{type(ase_atoms).__qualname__}"
            )
        return import_atoms(
            _atoms_from_ase(ase_atoms),
            forces=forces,
            stress=stress,
            energy=energy,
            charges=charges,
            magmoms=magmoms,
            force_symmetric=force_symmetric,
            drop_atomic_properties=drop_atomic_properties,
            fallback_full_atomic=fallback_full_atomic,
            symmetry_policy=symmetry_policy,
            custom=kwargs,
        )


class ASEExporter:
    """Convert USIF structures to ASE ``Atoms``."""

    @staticmethod
    def to_ase(structure: USIFStructure) -> Any:
        """Return an ``ase.Atoms``; energy/forces/stress are attached as a single-point result."""
        units, SinglePointCalculator = _require_ase()
        from ase import Atoms

        data = structure_to_arrays(structure)
        atoms = Atoms(
            numbers=data.numbers,
            positions=data.positions,
            cell=data.lattice if data.is_crystal else None,
            pbc=data.pbc if data.is_crystal else False,
        )
        charges = data.atomic_array("charge")
        if charges is not None:
            atoms.set_initial_charges(charges)
        magmoms = data.atomic_array("magmom")
        if magmoms is not None:
            atoms.set_initial_magnetic_moments(magmoms)
        velocities = data.atomic_array("velocity")
        if velocities is not None:
            atoms.set_velocities(velocities / units.fs)
        custom_keys = sorted({key for extra in data.site_custom for key in extra})
        for key in custom_keys:
            values = [extra.get(key) for extra in data.site_custom]
            if all(v is not None for v in values):
                try:
                    atoms.set_array(key, np.array(values))
                except (TypeError, ValueError):
                    logger.debug("Per-atom custom value %r cannot be an ASE array", key)

        for key, value in data.custom.items():
            atoms.info[key] = value

        results: Dict[str, Any] = {}
        if data.energy is not None:
            results["energy"] = data.energy
            atoms.info["energy"] = data.energy
        forces = data.atomic_array("force")
        if forces is not None:
            results["forces"] = forces
        if data.stress is not None:
            results["stress"] = voigt_to_tensor(data.stress) / EV_PER_ANG3_TO_GPA
        if results:
            atoms.calc = SinglePointCalculator(atoms, **results)
        return atoms
