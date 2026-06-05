"""pymatgen -> USIF importer facade."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from usif.interop.common import PymatgenObject, is_pymatgen_molecule, is_pymatgen_structure
from usif.interop.pymatgen.crystal_importer import CrystalImporter
from usif.interop.pymatgen.molecule_importer import MoleculeImporter
from usif.structures.structure import USIFStructure
from usif.symmetry.policies import SymmetryPolicy


class PymatgenImporter:
    """Dispatch pymatgen Structure or Molecule imports to focused importers."""

    @staticmethod
    def from_pymatgen(
        pmg_obj: PymatgenObject,
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
        """Convert a pymatgen Structure or Molecule to USIF.

        The public contract accepts concrete pymatgen ``Structure`` and
        ``Molecule`` objects.  Runtime type guards keep this adapter boundary
        explicit and produce a clear error for unsupported objects.
        """
        policy = symmetry_policy or SymmetryPolicy.from_import_flags(
            force_symmetric=force_symmetric,
            drop_atomic_properties=drop_atomic_properties,
            fallback_full_atomic=fallback_full_atomic,
        )

        if is_pymatgen_molecule(pmg_obj):
            return MoleculeImporter.from_pymatgen_molecule(
                pmg_obj,
                forces=forces,
                charges=charges,
                energy=energy,
                symmetry_policy=policy,
                **kwargs,
            )

        if is_pymatgen_structure(pmg_obj):
            return CrystalImporter.from_pymatgen_structure(
                pmg_obj,
                forces=forces,
                stress=stress,
                energy=energy,
                charges=charges,
                magmoms=magmoms,
                symmetry_policy=policy,
                **kwargs,
            )

        raise TypeError(
            "Expected pymatgen Structure or Molecule, "
            f"got {type(pmg_obj).__module__}.{type(pmg_obj).__qualname__}"
        )
