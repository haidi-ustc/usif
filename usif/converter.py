#!/usr/bin/env python3
"""Public structure conversion facade.

Heavy pymatgen/ASE conversion code lives under :mod:`usif.interop`.  This module
keeps the historical ``StructureConverter`` API while routing calls to the
adapter layer.
"""

from typing import Optional

import numpy as np

from usif.structures.structure import USIFStructure


class StructureConverter:
    """Backward-compatible facade for external structure conversions."""

    @staticmethod
    def from_pymatgen(
        pmg_obj,
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        force_symmetric: bool = False,
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        **kwargs,
    ) -> USIFStructure:
        from usif.interop.pymatgen.importer import PymatgenImporter

        return PymatgenImporter.from_pymatgen(
            pmg_obj,
            forces=forces,
            stress=stress,
            energy=energy,
            charges=charges,
            magmoms=magmoms,
            force_symmetric=force_symmetric,
            drop_atomic_properties=drop_atomic_properties,
            fallback_full_atomic=fallback_full_atomic,
            **kwargs,
        )

    @staticmethod
    def to_pymatgen(usif_structure: USIFStructure):
        from usif.interop.pymatgen.exporter import PymatgenExporter

        return PymatgenExporter.to_pymatgen(usif_structure)

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
        **kwargs,
    ) -> USIFStructure:
        from usif.interop.ase.importer import ASEImporter

        return ASEImporter.from_ase(
            ase_atoms,
            forces=forces,
            stress=stress,
            energy=energy,
            charges=charges,
            magmoms=magmoms,
            force_symmetric=force_symmetric,
            drop_atomic_properties=drop_atomic_properties,
            fallback_full_atomic=fallback_full_atomic,
            **kwargs,
        )

    @staticmethod
    def to_ase(usif_structure: USIFStructure):
        from usif.interop.ase.exporter import ASEExporter

        return ASEExporter.to_ase(usif_structure)

    # Compatibility wrappers for private helper methods that older tests or
    # downstream code may still call.  New code should use usif.symmetry.
    @staticmethod
    def _crystal_sites_match(pmg_structure, spacegroup_number, wyckoff_sites):
        from usif.symmetry import SymmetryOperations

        return SymmetryOperations.crystal_sites_match(
            pmg_structure, spacegroup_number, wyckoff_sites
        )

    @staticmethod
    def _molecular_sites_match(pmg_molecule, point_group, point_group_sites):
        from usif.symmetry import SymmetryOperations

        return SymmetryOperations.molecular_sites_match(
            pmg_molecule, point_group, point_group_sites
        )

    @staticmethod
    def _site_sets_equal(left, right, periodic):
        from usif.symmetry import SymmetryOperations

        return SymmetryOperations.site_sets_equal(left, right, periodic)

    @staticmethod
    def _coords_equal(left, right, periodic):
        from usif.symmetry import SymmetryOperations

        return SymmetryOperations.coords_equal(left, right, periodic)

    @staticmethod
    def _expand_fractional_orbit(coords, symmetry_ops, multiplicity):
        from usif.symmetry import SymmetryOperations

        return SymmetryOperations.expand_fractional_orbit(coords, symmetry_ops, multiplicity)

    @staticmethod
    def _expand_cartesian_orbit(coords, symmetry_ops, multiplicity):
        from usif.symmetry import SymmetryOperations

        return SymmetryOperations.expand_cartesian_orbit(coords, symmetry_ops, multiplicity)

    @staticmethod
    def _contains_coord(existing, candidate, periodic):
        from usif.symmetry import SymmetryOperations

        return SymmetryOperations.contains_coord(existing, candidate, periodic)
