"""Backend-neutral array conversion and type guards shared by all adapters."""

from usif.interop.common.arrays import (
    ATOMIC_FIELDS,
    AtomsData,
    build_structure,
    stress_to_voigt,
    structure_to_arrays,
    voigt_to_tensor,
)
from usif.interop.common.type_guards import (
    is_ase_atoms,
    is_matsimpy_crystal,
    is_matsimpy_molecule,
    is_matsimpy_object,
    is_pymatgen_molecule,
    is_pymatgen_object,
    is_pymatgen_structure,
)

__all__ = [
    "ATOMIC_FIELDS",
    "AtomsData",
    "build_structure",
    "is_ase_atoms",
    "is_matsimpy_crystal",
    "is_matsimpy_molecule",
    "is_matsimpy_object",
    "is_pymatgen_molecule",
    "is_pymatgen_object",
    "is_pymatgen_structure",
    "stress_to_voigt",
    "structure_to_arrays",
    "voigt_to_tensor",
]
