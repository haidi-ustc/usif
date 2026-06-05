"""Runtime type guards for optional external structure libraries."""

from __future__ import annotations

from typing import Any, TypeGuard

from usif.interop.common.protocols import ASEAtomsLike, PymatgenMoleculeLike, PymatgenStructureLike


def is_pymatgen_structure(obj: Any) -> TypeGuard[PymatgenStructureLike]:
    """Return whether ``obj`` is a concrete pymatgen ``Structure``."""
    try:
        from pymatgen.core import Structure as PMGStructure
    except ImportError:
        return False
    return isinstance(obj, PMGStructure)


def is_pymatgen_molecule(obj: Any) -> TypeGuard[PymatgenMoleculeLike]:
    """Return whether ``obj`` is a concrete pymatgen ``Molecule``."""
    try:
        from pymatgen.core import Molecule as PMGMolecule
    except ImportError:
        return False
    return isinstance(obj, PMGMolecule)


def is_pymatgen_object(obj: Any) -> TypeGuard[PymatgenStructureLike | PymatgenMoleculeLike]:
    """Return whether ``obj`` is a supported pymatgen structure object."""
    return is_pymatgen_structure(obj) or is_pymatgen_molecule(obj)


def is_ase_atoms(obj: Any) -> TypeGuard[ASEAtomsLike]:
    """Return whether ``obj`` is a concrete ASE ``Atoms`` object."""
    try:
        from ase import Atoms as ASEAtoms
    except ImportError:
        return False
    return isinstance(obj, ASEAtoms)


__all__ = [
    "is_ase_atoms",
    "is_pymatgen_molecule",
    "is_pymatgen_object",
    "is_pymatgen_structure",
]
