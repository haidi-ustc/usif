"""Import and export services for USIF structures.

USIF depends on no external structure library. Conversion to and from
matsimpy, pymatgen and ASE objects, and reading/writing foreign file formats,
use whichever of those optional packages is installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple, Union

import numpy as np

from usif.constants import CompressionType
from usif.interop.common import (
    is_ase_atoms,
    is_matsimpy_object,
    is_pymatgen_object,
    structure_to_arrays,
)
from usif.structures import USIFStructure
from usif.symmetry.policies import SymmetryPolicy

OBJECT_FORMATS = ("matsimpy", "pymatgen", "ase", "arrays")
_NATIVE_SUFFIXES = (".usif", ".json")


def _is_native_path(path: Path) -> bool:
    return path.suffix.lower() in _NATIVE_SUFFIXES


def _read_with_matsimpy(path: Path) -> Any:
    from matsimpy.io import read

    return read(str(path))


def _read_with_ase(path: Path) -> Any:
    from ase.io import read

    return read(str(path))


def _read_with_pymatgen(path: Path) -> Any:
    from pymatgen.core import Molecule, Structure

    try:
        return Structure.from_file(str(path))
    except Exception:
        return Molecule.from_file(str(path))


_FILE_READERS: List[Tuple[str, Callable[[Path], Any]]] = [
    ("matsimpy", _read_with_matsimpy),
    ("ase", _read_with_ase),
    ("pymatgen", _read_with_pymatgen),
]


def read_foreign_file(path: Union[str, Path]) -> Any:
    """Read a CIF/POSCAR/XYZ/... file with the first installed backend that can.

    Backends are tried in the order matsimpy, ASE, pymatgen.
    """
    path = Path(path)
    errors = []
    for name, reader in _FILE_READERS:
        try:
            return reader(path)
        except ImportError:
            continue
        except Exception as exc:  # backend installed but could not parse
            errors.append(f"{name}: {exc}")
    if not errors:
        raise ImportError(
            "Reading structure files other than .usif/.json needs matsimpy, ASE or "
            "pymatgen: pip install usif[matsimpy]"
        )
    raise ValueError(f"Could not read {path}: " + "; ".join(errors))


def import_structure(
    source: Union[str, Path, Any],
    /,
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
    """Create a USIFStructure from a file, or a matsimpy, pymatgen or ASE object.

    ``.usif``/``.json`` files are loaded natively; other files are read with an
    installed backend (see :func:`read_foreign_file`). Extra keyword arguments
    become structure-level custom properties.
    """
    options = dict(
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

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if _is_native_path(path):
            from usif.services.io import load_structure

            return load_structure(path)
        source = read_foreign_file(path)

    if is_matsimpy_object(source):
        from usif.interop.matsimpy import MatsimpyImporter

        return MatsimpyImporter.from_matsimpy(source, **options)
    if is_pymatgen_object(source):
        return import_pymatgen(source, **options)
    if is_ase_atoms(source):
        from usif.interop.ase import ASEImporter

        return ASEImporter.from_ase(source, **options)

    raise TypeError(
        f"Unsupported source type: {type(source)}. Supported: file path, "
        "matsimpy Crystal/Molecule, pymatgen Structure/Molecule, ase.Atoms"
    )


def import_pymatgen(pmg_obj: Any, /, **kwargs: Any) -> USIFStructure:
    """Create a USIFStructure from a pymatgen Structure or Molecule."""
    from usif.interop.pymatgen import PymatgenImporter

    return PymatgenImporter.from_pymatgen(pmg_obj, **kwargs)


def import_matsimpy(obj: Any, /, **kwargs: Any) -> USIFStructure:
    """Create a USIFStructure from a matsimpy Crystal or Molecule."""
    from usif.interop.matsimpy import MatsimpyImporter

    return MatsimpyImporter.from_matsimpy(obj, **kwargs)


def _to_object(structure: USIFStructure, fmt: str) -> Any:
    if fmt == "matsimpy":
        from usif.interop.matsimpy import MatsimpyExporter

        return MatsimpyExporter.to_matsimpy(structure)
    if fmt == "pymatgen":
        from usif.interop.pymatgen import PymatgenExporter

        return PymatgenExporter.to_pymatgen(structure)
    if fmt == "ase":
        from usif.interop.ase import ASEExporter

        return ASEExporter.to_ase(structure)
    return structure_to_arrays(structure)


def _write_foreign_file(structure: USIFStructure, path: Path, fmt: str, **kwargs: Any) -> None:
    """Write a non-USIF file format with the first installed backend that can."""
    errors = []
    try:
        from matsimpy.io import write

        write(_to_object(structure, "matsimpy"), str(path), format=fmt, **kwargs)
        return
    except ImportError:
        pass
    except Exception as exc:
        errors.append(f"matsimpy: {exc}")
    try:
        from ase.io import write as ase_write

        ase_write(str(path), _to_object(structure, "ase"), format=fmt, **kwargs)
        return
    except ImportError:
        pass
    except Exception as exc:
        errors.append(f"ase: {exc}")
    try:
        _to_object(structure, "pymatgen").to(str(path), fmt, **kwargs)
        return
    except ImportError:
        pass
    except Exception as exc:
        errors.append(f"pymatgen: {exc}")
    if not errors:
        raise ImportError(
            f"Writing '{fmt}' files needs matsimpy, ASE or pymatgen: pip install usif[matsimpy]"
        )
    raise ValueError(
        f"Format '{fmt}' is not supported by any installed backend: " + "; ".join(errors)
    )


def export_structure(
    structure: USIFStructure,
    filename: Optional[Union[str, Path]] = None,
    fmt: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Convert a USIFStructure to an object or write it to a file.

    * ``fmt`` in ``("matsimpy", "pymatgen", "ase", "arrays")`` with no filename
      returns an object (``"arrays"`` returns backend-free
      :class:`~usif.interop.common.AtomsData`).
    * ``.usif``/``.json`` filenames are written natively.
    * Other file formats (cif, poscar/vasp, xyz, ...) use an installed backend.
    """
    if filename is None:
        if fmt is None:
            raise ValueError(f"Specify fmt for object export, one of {OBJECT_FORMATS}")
        fmt = fmt.lower().strip().lstrip(".")
        if fmt not in OBJECT_FORMATS:
            raise ValueError(
                f"filename is required for '{fmt}' format "
                f"(object formats without a filename: {OBJECT_FORMATS})"
            )
        return _to_object(structure, fmt)

    path = Path(filename)
    if fmt is None:
        if path.name.lower().endswith(".usif.json"):
            fmt = "json"
        elif path.suffix:
            fmt = path.suffix[1:]
        else:
            raise ValueError(
                f"Cannot auto-detect format from filename '{filename}'. Please specify fmt."
            )
    fmt = fmt.lower().strip().lstrip(".")
    if fmt in OBJECT_FORMATS:
        raise ValueError(f"filename should not be provided for '{fmt}' format (returns object)")

    if fmt in {"usif", "json"}:
        from usif.services.io import save_structure

        compression = kwargs.get("compression", CompressionType.GZIP)
        save_structure(structure, path, compression=compression)
        return None

    _write_foreign_file(structure, path, fmt, **kwargs)
    return None
