"""Interoperability adapters for external structure libraries.

The package-level module exposes lightweight protocols and runtime type guards
eagerly. Concrete pymatgen/ASE adapters are resolved lazily so importing
``usif.services`` or ``usif.interop.common`` does not import optional adapter
classes before they are needed.
"""

from __future__ import annotations

from usif.interop.common import (
    ASEAtomsLike,
    PymatgenMoleculeLike,
    PymatgenObject,
    PymatgenStructureLike,
    is_ase_atoms,
    is_pymatgen_molecule,
    is_pymatgen_object,
    is_pymatgen_structure,
)

_LAZY_EXPORTS = {
    "ASEExporter": ("usif.interop.ase", "ASEExporter"),
    "ASEImporter": ("usif.interop.ase", "ASEImporter"),
    "PymatgenExporter": ("usif.interop.pymatgen", "PymatgenExporter"),
    "PymatgenImporter": ("usif.interop.pymatgen", "PymatgenImporter"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'usif.interop' has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = [
    "ASEAtomsLike",
    "ASEExporter",
    "ASEImporter",
    "PymatgenExporter",
    "PymatgenImporter",
    "PymatgenMoleculeLike",
    "PymatgenObject",
    "PymatgenStructureLike",
    "is_ase_atoms",
    "is_pymatgen_molecule",
    "is_pymatgen_object",
    "is_pymatgen_structure",
]
