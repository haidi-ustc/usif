"""Runtime type guards for optional external structure libraries.

The guards inspect the object's class lineage by qualified name, so checking a
value never imports pymatgen, ASE or matsimpy (and works when they are not
installed).
"""

from __future__ import annotations

from typing import Any


def _class_names(obj: Any) -> set[str]:
    return {f"{cls.__module__}.{cls.__qualname__}" for cls in type(obj).__mro__}


def _is_instance_of(obj: Any, module_prefix: str, qualname: str) -> bool:
    for name in _class_names(obj):
        module, _, cls = name.rpartition(".")
        if cls == qualname and (module == module_prefix or module.startswith(module_prefix + ".")):
            return True
    return False


def is_pymatgen_structure(obj: Any) -> bool:
    """Return whether ``obj`` is a pymatgen ``Structure`` (periodic)."""
    return _is_instance_of(obj, "pymatgen", "Structure") and not is_pymatgen_molecule(obj)


def is_pymatgen_molecule(obj: Any) -> bool:
    """Return whether ``obj`` is a pymatgen ``Molecule``."""
    return _is_instance_of(obj, "pymatgen", "Molecule")


def is_pymatgen_object(obj: Any) -> bool:
    """Return whether ``obj`` is a supported pymatgen structure object."""
    return is_pymatgen_structure(obj) or is_pymatgen_molecule(obj)


def is_ase_atoms(obj: Any) -> bool:
    """Return whether ``obj`` is an ASE ``Atoms`` object."""
    return _is_instance_of(obj, "ase", "Atoms")


def is_matsimpy_crystal(obj: Any) -> bool:
    """Return whether ``obj`` is a matsimpy ``Crystal``."""
    return _is_instance_of(obj, "matsimpy", "Crystal")


def is_matsimpy_molecule(obj: Any) -> bool:
    """Return whether ``obj`` is a matsimpy ``Molecule``."""
    return _is_instance_of(obj, "matsimpy", "Molecule")


def is_matsimpy_object(obj: Any) -> bool:
    """Return whether ``obj`` is a supported matsimpy structure object."""
    return is_matsimpy_crystal(obj) or is_matsimpy_molecule(obj)


__all__ = [
    "is_ase_atoms",
    "is_matsimpy_crystal",
    "is_matsimpy_molecule",
    "is_matsimpy_object",
    "is_pymatgen_molecule",
    "is_pymatgen_object",
    "is_pymatgen_structure",
]
