"""ASE -> USIF importer."""

from typing import Any, Optional

import numpy as np

from usif.structures.structure import USIFStructure

try:
    from ase import Atoms as ASEAtoms
except ImportError:  # pragma: no cover - exercised only without ASE installed
    ASEAtoms = None


class ASEImporter:
    """Import ASE Atoms objects into USIF."""

    @staticmethod
    def from_ase(
        ase_atoms,
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        force_symmetric: bool = False,
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        symmetry_policy: Optional[Any] = None,
        **kwargs,
    ) -> USIFStructure:
        """Convert an ASE Atoms object to USIF."""
        if ASEAtoms is None:
            raise ImportError("ASE is not installed. Install it with: pip install ase")
        if not isinstance(ase_atoms, ASEAtoms):
            raise TypeError(f"Expected ASE Atoms object, got {type(ase_atoms)}")

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

        from pymatgen.io.ase import AseAtomsAdaptor
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
