"""ASE -> USIF importer.

USIF's ASE adapter intentionally routes through pymatgen's ``AseAtomsAdaptor``.
That keeps ASE support aligned with the canonical pymatgen adapter and means the
ASE extra requires both ``ase`` and ``pymatgen`` at runtime.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from usif.interop.common import ASEAtomsLike, is_ase_atoms
from usif.structures.structure import USIFStructure
from usif.symmetry.policies import SymmetryPolicy


class ASEImporter:
    """Import ASE Atoms objects into USIF."""

    @staticmethod
    def from_ase(
        ase_atoms: ASEAtomsLike,
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
        """Convert an ASE Atoms object to USIF.

        ASE support depends on ``ase`` and pymatgen's ``AseAtomsAdaptor``.
        """
        if not is_ase_atoms(ase_atoms):
            raise TypeError(
                "Expected ASE Atoms object. Install ASE with `pip install usif[ase]` "
                f"and pass an ase.Atoms instance, got {type(ase_atoms).__module__}.{type(ase_atoms).__qualname__}."
            )

        if forces is None:
            try:
                forces = ase_atoms.get_forces()
            except (RuntimeError, AttributeError):
                pass
        if stress is None:
            try:
                stress = ase_atoms.get_stress(voigt=False)
            except (RuntimeError, AttributeError):
                pass
        if energy is None:
            try:
                energy = ase_atoms.get_potential_energy()
            except (RuntimeError, AttributeError):
                pass
        if charges is None:
            try:
                charges = ase_atoms.get_charges()
            except (RuntimeError, AttributeError):
                pass
        if magmoms is None:
            try:
                magmoms = ase_atoms.get_magnetic_moments()
            except (RuntimeError, AttributeError):
                pass

        try:
            has_cell = (
                ase_atoms.cell is not None
                and len(ase_atoms.cell) > 0
                and np.any(np.linalg.norm(ase_atoms.cell, axis=1) > 1e-10)
            )
        except (AttributeError, TypeError):
            has_cell = False

        try:
            from pymatgen.io.ase import AseAtomsAdaptor
        except ImportError as e:  # pragma: no cover - depends on optional runtime packaging
            raise ImportError(
                "ASE import requires pymatgen.io.ase.AseAtomsAdaptor. "
                "Install with `pip install usif[ase]`."
            ) from e
        from usif.interop.pymatgen.importer import PymatgenImporter

        adaptor = AseAtomsAdaptor()
        if has_cell:
            return PymatgenImporter.from_pymatgen(
                adaptor.get_structure(ase_atoms),
                forces=forces,
                stress=stress,
                energy=energy,
                charges=charges,
                magmoms=magmoms,
                force_symmetric=force_symmetric,
                drop_atomic_properties=drop_atomic_properties,
                fallback_full_atomic=fallback_full_atomic,
                symmetry_policy=symmetry_policy,
                **kwargs,
            )

        return PymatgenImporter.from_pymatgen(
            adaptor.get_molecule(ase_atoms),
            forces=forces,
            energy=energy,
            charges=charges,
            force_symmetric=force_symmetric,
            drop_atomic_properties=drop_atomic_properties,
            fallback_full_atomic=fallback_full_atomic,
            symmetry_policy=symmetry_policy,
            **kwargs,
        )
