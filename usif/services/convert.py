"""Import and export services for USIF structures."""

from pathlib import Path
from typing import Any, Optional, Union

import numpy as np

from usif.constants import CompressionType
from usif.structures import USIFStructure


def import_structure(
    source: Union[str, Path, Any],
    forces: Optional[np.ndarray] = None,
    stress: Optional[np.ndarray] = None,
    energy: Optional[float] = None,
    charges: Optional[np.ndarray] = None,
    magmoms: Optional[np.ndarray] = None,
    force_symmetric: bool = False,
    drop_atomic_properties: bool = False,
    fallback_full_atomic: bool = False,
    symmetry_policy: Optional[Any] = None,
    **kwargs: Any,
) -> USIFStructure:
    """Create a USIFStructure from a file path, pymatgen object, or ASE Atoms."""
    if isinstance(source, (str, Path)):
        file_path = Path(source)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            from pymatgen.core import Molecule as PMGMolecule
            from pymatgen.core import Structure as PMGStructure
        except ImportError as e:
            raise ImportError(
                "pymatgen is required for file reading. Install with: pip install pymatgen"
            ) from e

        try:
            pmg_obj = PMGStructure.from_file(str(file_path))
        except Exception:
            try:
                pmg_obj = PMGMolecule.from_file(str(file_path))
            except Exception as e:
                raise ValueError(
                    f"Could not read {file_path} as pymatgen Structure or Molecule. "
                    f"Supported formats: CIF, POSCAR, XYZ, etc."
                ) from e

        return import_pymatgen(
            pmg_obj,
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

    try:
        from pymatgen.core import Molecule as PMGMolecule
        from pymatgen.core import Structure as PMGStructure

        if isinstance(source, (PMGStructure, PMGMolecule)):
            return import_pymatgen(
                source,
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
    except ImportError:
        pass

    try:
        from ase import Atoms as ASEAtoms

        if isinstance(source, ASEAtoms):
            from usif.interop.ase.importer import ASEImporter

            return ASEImporter.from_ase(
                source,
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
    except ImportError:
        pass

    raise TypeError(
        f"Unsupported source type: {type(source)}. "
        f"Supported types: file path (str/Path), pymatgen Structure/Molecule, ASE Atoms"
    )


def import_pymatgen(
    pmg_obj: Any,
    forces: Optional[np.ndarray] = None,
    stress: Optional[np.ndarray] = None,
    energy: Optional[float] = None,
    charges: Optional[np.ndarray] = None,
    magmoms: Optional[np.ndarray] = None,
    force_symmetric: bool = False,
    drop_atomic_properties: bool = False,
    fallback_full_atomic: bool = False,
    symmetry_policy: Optional[Any] = None,
    **kwargs: Any,
) -> USIFStructure:
    """Create a USIFStructure from a pymatgen Structure or Molecule."""
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
        symmetry_policy=symmetry_policy,
        **kwargs,
    )


def export_structure(
    structure: USIFStructure,
    filename: Optional[Union[str, Path]] = None,
    fmt: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Convert a USIFStructure to another object or file format."""
    if fmt is None:
        if filename is None:
            fmt = "pymatgen"
        else:
            filename_path = Path(filename)
            ext = filename_path.suffix.lower()
            if not ext:
                raise ValueError(
                    f"Cannot auto-detect format from filename '{filename}'. "
                    f"Please specify fmt parameter."
                )
            fmt = ext[1:]

    fmt = fmt.lower().strip()
    if fmt.startswith("."):
        fmt = fmt[1:]

    if fmt == "pymatgen":
        if filename is not None:
            raise ValueError(
                "filename should not be provided for 'pymatgen' format (returns object)"
            )
        from usif.interop.pymatgen.exporter import PymatgenExporter

        return PymatgenExporter.to_pymatgen(structure)

    if fmt == "ase":
        if filename is not None:
            raise ValueError("filename should not be provided for 'ase' format (returns object)")
        from usif.interop.ase.exporter import ASEExporter

        return ASEExporter.to_ase(structure)

    if filename is None:
        raise ValueError(f"filename is required for '{fmt}' format")

    if fmt == "usif":
        from usif.services.io import save_structure

        compression = kwargs.get("compression", CompressionType.GZIP)
        save_structure(structure, filename, compression=compression)
        return None

    if fmt == "xyz":
        try:
            from usif.interop.ase.exporter import ASEExporter

            ase_atoms = ASEExporter.to_ase(structure)
            ase_atoms.write(str(filename))
            return None
        except ImportError as e:
            raise ImportError(
                "ASE is required for XYZ format. Install with: pip install ase"
            ) from e

    from usif.interop.pymatgen.exporter import PymatgenExporter

    pmg_obj = PymatgenExporter.to_pymatgen(structure)
    try:
        pmg_obj.to(str(filename), fmt, **kwargs)
        return None
    except Exception as e:
        raise ValueError(
            f"Format '{fmt}' is not supported. "
            f"Supported formats: usif, pymatgen, ase, xyz (via ASE), "
            f"and formats supported by pymatgen (cif, poscar, json, etc.). Error: {e}"
        ) from e
