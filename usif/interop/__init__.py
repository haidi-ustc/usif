"""Optional adapters for external structure libraries.

USIF itself depends on none of them. Install the one you use:

* ``pip install usif[matsimpy]`` -> :mod:`usif.interop.matsimpy`
* ``pip install usif[pymatgen]`` -> :mod:`usif.interop.pymatgen`
* ``pip install usif[ase]``      -> :mod:`usif.interop.ase`

Each adapter converts through :mod:`usif.interop.common.arrays`, so they all
produce identical USIF structures. Adapter classes are resolved lazily so that
importing :mod:`usif.interop` never imports an external library.
"""

from __future__ import annotations

from usif.interop.common import (
    AtomsData,
    build_structure,
    is_ase_atoms,
    is_matsimpy_crystal,
    is_matsimpy_molecule,
    is_matsimpy_object,
    is_pymatgen_molecule,
    is_pymatgen_object,
    is_pymatgen_structure,
    structure_to_arrays,
)

_LAZY_EXPORTS = {
    "ASEExporter": ("usif.interop.ase", "ASEExporter"),
    "ASEImporter": ("usif.interop.ase", "ASEImporter"),
    "MatsimpyExporter": ("usif.interop.matsimpy", "MatsimpyExporter"),
    "MatsimpyImporter": ("usif.interop.matsimpy", "MatsimpyImporter"),
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
    "ASEExporter",
    "ASEImporter",
    "AtomsData",
    "MatsimpyExporter",
    "MatsimpyImporter",
    "PymatgenExporter",
    "PymatgenImporter",
    "build_structure",
    "is_ase_atoms",
    "is_matsimpy_crystal",
    "is_matsimpy_molecule",
    "is_matsimpy_object",
    "is_pymatgen_molecule",
    "is_pymatgen_object",
    "is_pymatgen_structure",
    "structure_to_arrays",
]
