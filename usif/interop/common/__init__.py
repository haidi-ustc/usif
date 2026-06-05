"""Shared protocols and type guards for external-library adapters."""

from usif.interop.common.protocols import (
    ASEAtomsLike,
    NumericArray,
    PymatgenMoleculeLike,
    PymatgenObject,
    PymatgenSiteLike,
    PymatgenStructureLike,
)
from usif.interop.common.type_guards import (
    is_ase_atoms,
    is_pymatgen_molecule,
    is_pymatgen_object,
    is_pymatgen_structure,
)

__all__ = [
    "ASEAtomsLike",
    "NumericArray",
    "PymatgenMoleculeLike",
    "PymatgenObject",
    "PymatgenSiteLike",
    "PymatgenStructureLike",
    "is_ase_atoms",
    "is_pymatgen_molecule",
    "is_pymatgen_object",
    "is_pymatgen_structure",
]
