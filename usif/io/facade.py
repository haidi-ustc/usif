"""Application-level I/O and conversion facade for USIF structures.

This module centralizes the compatibility functions that used to be reached
through methods on ``USIFStructure``.  ``USIFStructure`` keeps those methods, but
new code can import these functions directly to avoid growing the domain model.
"""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np

from usif.constants import CompressionType


def from_source(
    source: Union[str, Path, Any],
    forces: Optional[np.ndarray] = None,
    stress: Optional[np.ndarray] = None,
    energy: Optional[float] = None,
    charges: Optional[np.ndarray] = None,
    magmoms: Optional[np.ndarray] = None,
    force_symmetric: bool = False,
    drop_atomic_properties: bool = False,
    fallback_full_atomic: bool = False,
    **kwargs,
):
    from usif.structures.source import from_source as _from_source

    return _from_source(
        source,
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
):
    from usif.structures.source import from_pymatgen as _from_pymatgen

    return _from_pymatgen(
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


def convert_to(structure, filename=None, fmt=None, **kwargs):
    from usif.structures.source import convert_to as _convert_to

    return _convert_to(structure, filename=filename, fmt=fmt, **kwargs)


def save_structure(structure, filename: Union[str, Path], compression=CompressionType.GZIP):
    from usif.structures.io import save_structure as _save_structure

    return _save_structure(structure, filename, compression=compression)


def load_structure(cls, filename: Union[str, Path]):
    from usif.structures.io import load_structure as _load_structure

    return _load_structure(cls, filename)
