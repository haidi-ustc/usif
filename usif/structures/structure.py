#!/usr/bin/env python3
"""
USIF Structure Module

This module provides the USIFStructure class, the core structure representation
for the USIF format. It supports both periodic (crystals) and non-periodic
(molecules) structures with two storage modes: symmetric and full atomic.

Main Class:
    USIFStructure: Universal structure representation for crystals and molecules

Structure Types:
    - CRYSTAL: Periodic structures with lattice (uses Wyckoff sites or atom sites)
    - MOLECULE: Non-periodic molecular structures (uses point group sites or atom sites)

Storage Modes:
    - SYMMETRIC: Store only unique sites with multiplicities (compact, for symmetric structures)
    - FULL_ATOMIC: Store all atoms explicitly (supports per-atom properties)

Features:
    - Unified representation for crystals and molecules
    - Automatic symmetry analysis support
    - Property attachment (atomic and structure-level)
    - File I/O with compression
    - MSONable for JSON serialization
    - Rich string representation

Usage:
    >>> from usif import USIFStructure, StructureType, StorageMode
    >>> from usif.structures.sites import WyckoffSite
    >>> import numpy as np
    >>>
    >>> # Create crystal structure
    >>> lattice = np.array([[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]])
    >>> sites = [WyckoffSite(atomic_number=14, multiplicity=8, coords=(0.0, 0.0, 0.0))]
    >>> structure = USIFStructure(
    ...     structure_type=StructureType.CRYSTAL,
    ...     storage_mode=StorageMode.SYMMETRIC,
    ...     lattice_matrix=lattice,
    ...     spacegroup=227,
    ...     wyckoff_sites=sites,
    ...     formula='Si'
    ... )
    >>>
    >>> # Save and load
    >>> structure.save('structure.usif')
    >>> loaded = USIFStructure.load('structure.usif')
    >>>
    >>> # Check structure properties
    >>> structure.is_crystal()  # True
    >>> structure.is_symmetric()  # True
    >>> structure.num_atoms()  # 8
    >>> print(structure)  # Pretty-printed representation

See Also:
    - StructureConverter: Convert from pymatgen
    - WyckoffSite, PointGroupSite, AtomSite: Site types
    - StructureProperties, AtomicProperties: Property types
"""

from pathlib import Path
from typing import Any, List, Optional, Union

import numpy as np
from monty.json import MSONable

from usif.constants import CompressionType, StorageMode, StructureType
from usif.exceptions import StorageError, ValidationError
from usif.properties.atomic import AtomicProperties
from usif.properties.structure import StructureProperties
from usif.structures.sites import AtomSite, PointGroupSite, WyckoffSite


class USIFStructure(MSONable):
    """
    Universal structure representation

    Structure type matrix:
    ┌─────────────┬──────────────┬─────────────────┐
    │             │ SYMMETRIC    │ FULL_ATOMIC     │
    ├─────────────┼──────────────┼─────────────────┤
    │ CRYSTAL     │ Wyckoff      │ All atoms       │
    │ (Periodic)  │ + lattice    │ + lattice       │
    ├─────────────┼──────────────┼─────────────────┤
    │ MOLECULE    │ Point group  │ All atoms       │
    │ (Molecular) │ (no lattice) │ (no lattice)    │
    └─────────────┴──────────────┴─────────────────┘
    """

    __slots__ = [
        "structure_type",
        "storage_mode",
        "lattice_matrix",
        "spacegroup",
        "point_group",
        "wyckoff_sites",
        "point_group_sites",
        "atom_sites",
        "structure_properties",
        "formula",
    ]

    def __init__(
        self,
        structure_type: StructureType = StructureType.CRYSTAL,
        storage_mode: StorageMode = StorageMode.SYMMETRIC,
        lattice_matrix: Optional[np.ndarray] = None,
        spacegroup: int = 1,
        point_group: Optional[str] = None,
        wyckoff_sites: Optional[List[WyckoffSite]] = None,
        point_group_sites: Optional[List[PointGroupSite]] = None,
        atom_sites: Optional[List[AtomSite]] = None,
        structure_properties: Optional[StructureProperties] = None,
        formula: str = "",
    ):
        """
        Initialize USIFStructure

        Creates a new USIFStructure instance representing either a crystal (periodic)
        or molecule (non-periodic) structure. The structure can use symmetric storage
        (compact, for symmetric structures) or full atomic storage (explicit atoms,
        supports per-atom properties).

        Args:
            structure_type: CRYSTAL for periodic structures, MOLECULE for non-periodic
            storage_mode: SYMMETRIC for compact storage, FULL_ATOMIC for explicit atoms
            lattice_matrix: 3x3 lattice matrix (required for crystals, None for molecules)
            spacegroup: Space group number (for crystals, default: 1)
            point_group: Point group symbol (for molecules, e.g., "C2v")
            wyckoff_sites: List of Wyckoff sites (for CRYSTAL + SYMMETRIC mode)
            point_group_sites: List of point group sites (for MOLECULE + SYMMETRIC mode)
            atom_sites: List of atom sites (for FULL_ATOMIC mode)
            structure_properties: Structure-level properties (energy, stress, etc.)
            formula: Chemical formula string

        Raises:
            ValidationError: If structure configuration is invalid

        Example:
            >>> from usif import USIFStructure, StructureType, StorageMode
            >>> from usif.structures.sites import WyckoffSite
            >>> import numpy as np
            >>>
            >>> # Create crystal structure
            >>> lattice = np.array([[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]])
            >>> sites = [WyckoffSite(atomic_number=14, multiplicity=8, coords=(0.0, 0.0, 0.0))]
            >>> structure = USIFStructure(
            ...     structure_type=StructureType.CRYSTAL,
            ...     storage_mode=StorageMode.SYMMETRIC,
            ...     lattice_matrix=lattice,
            ...     spacegroup=227,
            ...     wyckoff_sites=sites,
            ...     formula='Si'
            ... )
        """
        self.structure_type = structure_type
        self.storage_mode = storage_mode
        self.lattice_matrix = lattice_matrix
        self.spacegroup = spacegroup
        self.point_group = point_group
        self.wyckoff_sites = wyckoff_sites
        self.point_group_sites = point_group_sites
        self.atom_sites = atom_sites
        self.structure_properties = (
            structure_properties
            if structure_properties is not None
            else StructureProperties()
        )
        self.formula = formula

        self._validate_structure()

    def _validate_structure(self) -> None:
        """Validate structure configuration"""
        if self.structure_type == StructureType.MOLECULE:
            if self.lattice_matrix is not None:
                raise ValidationError("Molecular structures should not have lattice")
            if self.storage_mode == StorageMode.SYMMETRIC:
                if self.point_group_sites is None or len(self.point_group_sites) == 0:
                    raise ValidationError(
                        "Molecular SYMMETRIC mode requires non-empty point_group_sites"
                    )
            elif self.storage_mode == StorageMode.FULL_ATOMIC:
                if self.atom_sites is None or len(self.atom_sites) == 0:
                    raise ValidationError(
                        "Molecular FULL_ATOMIC mode requires non-empty atom_sites"
                    )
        else:
            if self.lattice_matrix is None:
                raise ValidationError("Crystal structures require lattice")
            if self.storage_mode == StorageMode.SYMMETRIC:
                if self.wyckoff_sites is None or len(self.wyckoff_sites) == 0:
                    raise ValidationError(
                        "Crystal SYMMETRIC mode requires non-empty wyckoff_sites"
                    )
            elif self.storage_mode == StorageMode.FULL_ATOMIC:
                if self.atom_sites is None or len(self.atom_sites) == 0:
                    raise ValidationError(
                        "Crystal FULL_ATOMIC mode requires non-empty atom_sites"
                    )

    def is_crystal(self) -> bool:
        """
        Check if structure is a crystal (periodic)

        Returns:
            bool: True if structure is periodic (has lattice), False otherwise

        Example:
            >>> structure.is_crystal()  # True for crystals
        """
        return self.structure_type == StructureType.CRYSTAL

    def is_molecular(self) -> bool:
        """
        Check if structure is a molecule (non-periodic)

        Returns:
            bool: True if structure is non-periodic (no lattice), False otherwise

        Example:
            >>> structure.is_molecular()  # True for molecules
        """
        return self.structure_type == StructureType.MOLECULE

    def is_symmetric(self) -> bool:
        """
        Check if structure uses symmetric storage mode

        Returns:
            bool: True if using SYMMETRIC storage (compact), False if FULL_ATOMIC

        Example:
            >>> structure.is_symmetric()  # True for symmetric storage
        """
        return self.storage_mode == StorageMode.SYMMETRIC

    def num_atoms(self) -> int:
        """
        Get total number of atoms in the structure

        For symmetric storage, calculates from site multiplicities.
        For full atomic storage, returns the count of atom sites.

        Returns:
            int: Total number of atoms

        Example:
            >>> n_atoms = structure.num_atoms()
            >>> print(f"Structure has {n_atoms} atoms")
        """
        if self.storage_mode == StorageMode.SYMMETRIC:
            if self.is_crystal():
                if self.wyckoff_sites is None:
                    return 0
                return sum(site.multiplicity for site in self.wyckoff_sites)
            else:
                if self.point_group_sites is None:
                    return 0
                return sum(site.multiplicity for site in self.point_group_sites)
        else:
            if self.atom_sites is None:
                return 0
            return len(self.atom_sites)

    def as_dict(self) -> dict:
        """
        Convert USIFStructure to MSONable dictionary

        Converts the structure to a dictionary format compatible with the
        Materials Science Object Notation (MSON) standard, allowing for
        JSON serialization and deserialization.

        Returns:
            dict: Dictionary representation with all structure data

        Example:
            >>> structure_dict = structure.as_dict()
            >>> import json
            >>> json_str = json.dumps(structure_dict)
        """
        d = {
            "@module": self.__class__.__module__,
            "@class": self.__class__.__name__,
            "structure_type": self.structure_type.value,
            "storage_mode": self.storage_mode.value,
            "spacegroup": self.spacegroup,
            "point_group": self.point_group,
            "structure_properties": self.structure_properties,
            "formula": self.formula,
        }

        if self.lattice_matrix is not None:
            d["lattice_matrix"] = self.lattice_matrix.tolist()

        if self.wyckoff_sites is not None:
            d["wyckoff_sites"] = [
                {
                    "atomic_number": site.atomic_number,
                    "multiplicity": site.multiplicity,
                    "coords": site.coords,
                    "occupancy": site.occupancy,
                }
                for site in self.wyckoff_sites
            ]

        if self.point_group_sites is not None:
            d["point_group_sites"] = [
                {
                    "atomic_number": site.atomic_number,
                    "multiplicity": site.multiplicity,
                    "coords": site.coords,
                    "occupancy": site.occupancy,
                }
                for site in self.point_group_sites
            ]

        if self.atom_sites is not None:
            d["atom_sites"] = [
                {
                    "atomic_number": site.atomic_number,
                    "coords": site.coords,
                    "properties": {
                        "force": site.properties.force,
                        "charge": site.properties.charge,
                        "magmom": site.properties.magmom,
                        "velocity": site.properties.velocity,
                        "custom": site.properties.custom,
                    },
                }
                for site in self.atom_sites
            ]

        return d

    @classmethod
    def from_dict(cls, d: dict) -> "USIFStructure":
        """
        Create USIFStructure from MSONable dictionary

        Reconstructs a USIFStructure from a dictionary created by as_dict().
        This is the inverse operation of as_dict().

        Args:
            d: Dictionary representation from as_dict()

        Returns:
            USIFStructure: Reconstructed structure instance

        Example:
            >>> structure_dict = structure.as_dict()
            >>> reconstructed = USIFStructure.from_dict(structure_dict)
        """
        lattice_matrix = None
        if "lattice_matrix" in d and d["lattice_matrix"] is not None:
            lattice_matrix = np.array(d["lattice_matrix"])

        wyckoff_sites = None
        if "wyckoff_sites" in d and d["wyckoff_sites"] is not None:
            wyckoff_sites = []
            for site_dict in d["wyckoff_sites"]:
                wyckoff_sites.append(WyckoffSite(**site_dict))

        point_group_sites = None
        if "point_group_sites" in d and d["point_group_sites"] is not None:
            point_group_sites = []
            for site_dict in d["point_group_sites"]:
                point_group_sites.append(PointGroupSite(**site_dict))

        atom_sites = None
        if "atom_sites" in d and d["atom_sites"] is not None:
            atom_sites = []
            for site_dict in d["atom_sites"]:
                props_dict = site_dict.get("properties", {})
                atom_props = AtomicProperties(
                    force=props_dict.get("force"),
                    charge=props_dict.get("charge"),
                    magmom=props_dict.get("magmom"),
                    velocity=props_dict.get("velocity"),
                    custom=props_dict.get("custom", {}),
                )
                atom_sites.append(
                    AtomSite(
                        atomic_number=site_dict["atomic_number"],
                        coords=site_dict["coords"],
                        properties=atom_props,
                    )
                )

        structure_properties = None
        if "structure_properties" in d:
            if isinstance(d["structure_properties"], dict):
                structure_properties = StructureProperties(**d["structure_properties"])
            else:
                structure_properties = d["structure_properties"]

        return cls(
            structure_type=StructureType(d["structure_type"]),
            storage_mode=StorageMode(d["storage_mode"]),
            lattice_matrix=lattice_matrix,
            spacegroup=d["spacegroup"],
            point_group=d.get("point_group"),
            wyckoff_sites=wyckoff_sites,
            point_group_sites=point_group_sites,
            atom_sites=atom_sites,
            structure_properties=structure_properties,
            formula=d["formula"],
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, USIFStructure):
            return False

        lattice_equal = True
        if self.lattice_matrix is not None and other.lattice_matrix is not None:
            from usif.constants import SymmetryConstants

            lattice_equal = np.allclose(
                self.lattice_matrix,
                other.lattice_matrix,
                atol=SymmetryConstants.COORDINATE_TOLERANCE,
            )
        elif self.lattice_matrix != other.lattice_matrix:
            lattice_equal = False

        return (
            self.structure_type == other.structure_type
            and self.storage_mode == other.storage_mode
            and lattice_equal
            and self.spacegroup == other.spacegroup
            and self.point_group == other.point_group
            and self.wyckoff_sites == other.wyckoff_sites
            and self.point_group_sites == other.point_group_sites
            and self.atom_sites == other.atom_sites
            and self.structure_properties == other.structure_properties
            and self.formula == other.formula
        )

    def __repr__(self) -> str:
        """Unambiguous string representation for debugging"""
        parts = [
            f"structure_type={self.structure_type.name}",
            f"storage_mode={self.storage_mode.name}",
            f"formula='{self.formula}'",
            f"atoms={self.num_atoms()}",
        ]

        if self.is_crystal():
            parts.append(f"spacegroup={self.spacegroup}")
            if self.lattice_matrix is not None:
                # Show lattice parameters (a, b, c lengths)
                lengths = np.linalg.norm(self.lattice_matrix, axis=1)
                parts.append(
                    f"lattice=({lengths[0]:.3f}, {lengths[1]:.3f}, {lengths[2]:.3f})"
                )
        else:
            if self.point_group:
                parts.append(f"point_group='{self.point_group}'")

        if self.structure_properties.energy is not None:
            parts.append(f"energy={self.structure_properties.energy:.6f}")

        return f"USIFStructure({', '.join(parts)})"

    def __str__(self) -> str:
        """Human-readable string representation"""
        lines = []

        # Header with type and formula
        struct_type_str = "Crystal" if self.is_crystal() else "Molecule"
        lines.append(f"{struct_type_str}: {self.formula or 'Unknown'}")

        # Basic info
        lines.append(f"  Atoms: {self.num_atoms()}")
        lines.append(f"  Storage: {self.storage_mode.name}")

        # Structure-specific info
        if self.is_crystal():
            if self.lattice_matrix is not None:
                lengths = np.linalg.norm(self.lattice_matrix, axis=1)
                angles = []
                for i in range(3):
                    j, k = (i + 1) % 3, (i + 2) % 3
                    v1 = self.lattice_matrix[j] / lengths[j]
                    v2 = self.lattice_matrix[k] / lengths[k]
                    angle = np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0)) * 180 / np.pi
                    angles.append(angle)
                lines.append(
                    f"  Lattice: a={lengths[0]:.3f} Å, b={lengths[1]:.3f} Å, c={lengths[2]:.3f} Å"
                )
                lines.append(
                    f"  Angles: α={angles[0]:.1f}°, β={angles[1]:.1f}°, γ={angles[2]:.1f}°"
                )
            lines.append(f"  Spacegroup: {self.spacegroup}")
            if self.storage_mode == StorageMode.SYMMETRIC and self.wyckoff_sites:
                lines.append(f"  Wyckoff sites: {len(self.wyckoff_sites)}")
        else:
            if self.point_group:
                lines.append(f"  Point group: {self.point_group}")
            if self.storage_mode == StorageMode.SYMMETRIC and self.point_group_sites:
                lines.append(f"  Symmetry sites: {len(self.point_group_sites)}")

        # Properties
        from usif.units import Units

        props = []
        if self.structure_properties.energy is not None:
            props.append(f"E={self.structure_properties.energy:.6f} {Units.EV}")
        if self.structure_properties.volume is not None:
            props.append(
                f"V={self.structure_properties.volume:.3f} {Units.ANGSTROM_CUBED}"
            )
        if self.structure_properties.pressure is not None:
            props.append(f"P={self.structure_properties.pressure:.3f} {Units.GPA}")
        if props:
            lines.append(f"  Properties: {', '.join(props)}")

        return "\n".join(lines)

    @classmethod
    def from_source(
        cls,
        source: Union[str, Path, Any],
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        force_symmetric: bool = False,
        **kwargs,
    ) -> "USIFStructure":
        """
        High-level interface to create USIFStructure from various sources

        This is the recommended method for creating USIF structures. It automatically
        detects the input type and handles conversion from:
        - File paths (CIF, POSCAR, XYZ, etc.) - uses pymatgen to read
        - Pymatgen Structure or Molecule objects
        - ASE Atoms objects

        All sources support property attachment (forces, stress, energy, etc.)

        Note: Due to Python's reserved keyword restrictions, the method is named
        `from_source()`, but you can also access it as `from()` via attribute access.
        However, `from_source()` is the recommended way to call it.

        Args:
            source: Input source - can be:
                   - File path (str or Path): Any format supported by pymatgen
                   - Pymatgen Structure or Molecule object
                   - ASE Atoms object
            forces: Optional forces array (Nx3 for N atoms, in eV/Å)
            stress: Optional stress tensor (3x3 or 6-element Voigt notation, in GPa)
            energy: Optional total energy (in eV)
            charges: Optional atomic charges array (N elements, in e)
            magmoms: Optional magnetic moments array (N elements, in μB)
            force_symmetric: Force symmetric storage mode (default: auto-detect)
            **kwargs: Additional properties to store in structure_properties.custom

        Returns:
            USIFStructure instance with automatic symmetry analysis

        Raises:
            FileNotFoundError: If file path doesn't exist
            ImportError: If required dependencies (pymatgen/ASE) are missing
            SymmetryAnalysisError: If symmetry analysis fails
            ValidationError: If input data is invalid

        Example:
            >>> from usif import USIFStructure
            >>> from pymatgen.core import Structure
            >>> from ase import Atoms
            >>>
            >>> # From file (recommended: use from_source)
            >>> usif_struct = USIFStructure.from_source("structure.cif", energy=-10.5)
            >>>
            >>> # From pymatgen object
            >>> pmg_struct = Structure.from_file("structure.cif")
            >>> usif_struct = USIFStructure.from_source(pmg_struct, energy=-10.5)
            >>>
            >>> # From ASE object
            >>> ase_atoms = Atoms('H2O', positions=[[0, 0, 0], [0.95, 0, 0], [0.95, 0.95, 0]])
            >>> usif_struct = USIFStructure.from_source(ase_atoms, energy=-10.5, calculator="VASP")
        """
        from usif.converter import StructureConverter

        # Check if it's a file path
        if isinstance(source, (str, Path)):
            file_path = Path(source)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Use pymatgen to read the file
            try:
                from pymatgen.core import Molecule as PMGMolecule
                from pymatgen.core import Structure as PMGStructure

                # Try as Structure first (for periodic systems)
                try:
                    pmg_obj = PMGStructure.from_file(str(file_path))
                except Exception:
                    # Try as Molecule (for non-periodic systems)
                    try:
                        pmg_obj = PMGMolecule.from_file(str(file_path))
                    except Exception:
                        raise ValueError(
                            f"Could not read {file_path} as pymatgen Structure or Molecule. "
                            f"Supported formats: CIF, POSCAR, XYZ, etc."
                        )

                return StructureConverter.from_pymatgen(
                    pmg_obj,
                    forces=forces,
                    stress=stress,
                    energy=energy,
                    charges=charges,
                    magmoms=magmoms,
                    force_symmetric=force_symmetric,
                    **kwargs,
                )
            except ImportError:
                raise ImportError(
                    "pymatgen is required for file reading. Install with: pip install pymatgen"
                )

        # Check if it's a pymatgen object
        try:
            from pymatgen.core import Molecule as PMGMolecule
            from pymatgen.core import Structure as PMGStructure

            if isinstance(source, (PMGStructure, PMGMolecule)):
                return StructureConverter.from_pymatgen(
                    source,
                    forces=forces,
                    stress=stress,
                    energy=energy,
                    charges=charges,
                    magmoms=magmoms,
                    force_symmetric=force_symmetric,
                    **kwargs,
                )
        except ImportError:
            pass  # pymatgen not available, continue to check ASE

        # Check if it's an ASE Atoms object
        try:
            from ase import Atoms as ASEAtoms

            if isinstance(source, ASEAtoms):
                return StructureConverter.from_ase(
                    source,
                    forces=forces,
                    stress=stress,
                    energy=energy,
                    charges=charges,
                    magmoms=magmoms,
                    force_symmetric=force_symmetric,
                    **kwargs,
                )
        except ImportError:
            pass  # ASE not available

        # If we get here, we don't recognize the type
        raise TypeError(
            f"Unsupported source type: {type(source)}. "
            f"Supported types: file path (str/Path), pymatgen Structure/Molecule, ASE Atoms"
        )

    @classmethod
    def from_pymatgen(
        cls,
        pmg_obj,
        forces: Optional[np.ndarray] = None,
        stress: Optional[np.ndarray] = None,
        energy: Optional[float] = None,
        charges: Optional[np.ndarray] = None,
        magmoms: Optional[np.ndarray] = None,
        force_symmetric: bool = False,
        **kwargs,
    ) -> "USIFStructure":
        """
        Create USIFStructure from pymatgen Structure or Molecule

        This is a convenient class method that automatically handles symmetry
        analysis and Wyckoff site extraction from pymatgen objects.

        Note: For a more flexible interface that supports files and ASE objects,
        use USIFStructure.from_source() instead.

        Args:
            pmg_obj: Pymatgen Structure or Molecule object
            forces: Optional forces array (Nx3)
            stress: Optional stress tensor (3x3 or 6-element Voigt)
            energy: Optional energy value
            charges: Optional atomic charges array
            magmoms: Optional magnetic moments array
            force_symmetric: Force symmetric storage mode (default: auto-detect)
            **kwargs: Additional properties to store in structure_properties.custom

        Returns:
            USIFStructure instance with automatic symmetry analysis

        Example:
            >>> from pymatgen.core import Structure
            >>> pmg_struct = Structure.from_file("structure.cif")
            >>> usif_struct = USIFStructure.from_pymatgen(
            ...     pmg_struct,
            ...     energy=-10.5,
            ...     calculator="VASP"
            ... )

        See Also:
            USIFStructure.from_source(): High-level interface supporting files, pymatgen, and ASE
        """
        from usif.converter import StructureConverter

        return StructureConverter.from_pymatgen(
            pmg_obj,
            forces=forces,
            stress=stress,
            energy=energy,
            charges=charges,
            magmoms=magmoms,
            force_symmetric=force_symmetric,
            **kwargs,
        )

    def to(
        self,
        filename: Optional[Union[str, Path]] = None,
        fmt: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Convert structure to various formats (similar to pymatgen's to() method)

        Supports conversion to:
        - "usif" or ".usif": Save to USIF format (returns None, saves to file)
        - "pymatgen": Convert to pymatgen Structure/Molecule (returns object)
        - "ase": Convert to ASE Atoms (returns object)
        - "xyz": Save to XYZ format (uses ASE, requires ase package)
        - File formats: "cif", "poscar", "json", etc. (saves to file via pymatgen)

        Args:
            filename: Optional output file path. If provided and fmt is None,
                     format is auto-detected from file extension.
            fmt: Optional format string (e.g., "usif", "pymatgen", "ase", "cif", "poscar").
                 If None and filename is provided, format is inferred from filename extension.
                 If None and filename is None, defaults to "pymatgen" for object return.
            **kwargs: Additional arguments passed to save/conversion methods
                     - compression: For "usif" format (CompressionType enum)

        Returns:
            - For "pymatgen": Returns pymatgen Structure or Molecule
            - For "ase": Returns ASE Atoms object
            - For file formats ("usif", "cif", etc.): Returns None (saves to file)

        Raises:
            ValueError: If format is not supported or filename is missing for file formats
            ImportError: If required dependencies are missing

        Example:
            >>> # Save to USIF format (auto-detect from extension)
            >>> structure.to("output.usif")
            >>> structure.to("output.usif", "usif", compression=CompressionType.GZIP)

            >>> # Convert to pymatgen (no filename needed)
            >>> pmg_struct = structure.to(fmt="pymatgen")
            >>> pmg_struct = structure.to(None, "pymatgen")

            >>> # Convert to ASE (no filename needed)
            >>> ase_atoms = structure.to(fmt="ase")

            >>> # Save to various file formats (auto-detect from extension)
            >>> structure.to("output.cif")  # Auto-detects CIF format
            >>> structure.to("output.poscar")  # Auto-detects POSCAR format
            >>> structure.to("output.xyz")  # Auto-detects XYZ format
            >>> structure.to("output.cif", "cif")  # Explicit format
        """
        # Auto-detect format from filename if fmt is not provided
        if fmt is None:
            if filename is None:
                # Default to pymatgen if no filename and no format specified
                fmt = "pymatgen"
            else:
                # Extract format from file extension
                filename_path = Path(filename)
                ext = filename_path.suffix.lower()
                if ext:
                    fmt = ext[1:]  # Remove leading dot
                else:
                    raise ValueError(
                        f"Cannot auto-detect format from filename '{filename}'. "
                        f"Please specify fmt parameter."
                    )

        fmt = fmt.lower().strip()

        # Normalize format string (remove leading dot if present)
        if fmt.startswith("."):
            fmt = fmt[1:]

        # Pymatgen format (object return, no filename needed)
        if fmt == "pymatgen":
            if filename is not None:
                raise ValueError(
                    "filename should not be provided for 'pymatgen' format (returns object)"
                )
            from usif.converter import StructureConverter

            return StructureConverter.to_pymatgen(self)

        # ASE format (object return, no filename needed)
        if fmt == "ase":
            if filename is not None:
                raise ValueError(
                    "filename should not be provided for 'ase' format (returns object)"
                )
            from usif.converter import StructureConverter

            return StructureConverter.to_ase(self)

        # All other formats require a filename
        if filename is None:
            raise ValueError(f"filename is required for '{fmt}' format")

        # USIF format
        if fmt == "usif":
            compression = kwargs.get("compression", CompressionType.GZIP)
            self.save(filename, compression=compression)
            return None

        # XYZ format - use ASE (pymatgen doesn't support XYZ directly)
        if fmt == "xyz":
            try:
                from usif.converter import StructureConverter

                ase_atoms = StructureConverter.to_ase(self)
                ase_atoms.write(str(filename))
                return None
            except ImportError:
                raise ImportError(
                    "ASE is required for XYZ format. Install with: pip install ase"
                )

        # File formats via pymatgen
        # Supported formats: cif, poscar, json, etc.
        from usif.converter import StructureConverter

        pmg_obj = StructureConverter.to_pymatgen(self)

        # Use pymatgen's to() method to save in the requested format
        # Note: pymatgen's to() signature is to(filename, fmt, **kwargs)
        try:
            pmg_obj.to(str(filename), fmt, **kwargs)
            return None
        except Exception as e:
            raise ValueError(
                f"Format '{fmt}' is not supported. "
                f"Supported formats: usif, pymatgen, ase, xyz (via ASE), "
                f"and formats supported by pymatgen (cif, poscar, json, etc.). Error: {e}"
            ) from e

    def save(
        self,
        filename: Union[str, Path],
        compression: CompressionType = CompressionType.GZIP,
    ) -> None:
        """
        Save structure to file

        Automatically uses USIF encoder when file extension is .usif,
        otherwise saves as JSON (MSONable format).

        Args:
            filename: Output file path
            compression: Compression type for .usif files (ignored for JSON)

        Example:
            >>> structure.save("structure.usif")  # Uses USIF encoder
            >>> structure.save("structure.json")  # Uses JSON format
        """
        filename = Path(filename)

        if filename.suffix.lower() == ".usif":
            # Use USIF encoder for .usif files
            from usif.encoder import USIF

            encoder = USIF(compression=compression)
            encoder.save(self, filename)
        else:
            # Use MSONable JSON format for other files
            try:
                from monty.serialization import dumpfn

                dumpfn(self, filename, indent=2)
            except IOError as e:
                raise StorageError(
                    f"Failed to save structure to {filename}: {e}"
                ) from e

    @classmethod
    def load(cls, filename: Union[str, Path]) -> "USIFStructure":
        """
        Load structure from file

        Automatically detects format based on file extension:
        - .usif files: Uses USIF decoder
        - Other files: Uses JSON (MSONable format)

        Args:
            filename: Input file path

        Returns:
            USIFStructure instance

        Example:
            >>> structure = USIFStructure.load("structure.usif")
            >>> structure = USIFStructure.load("structure.json")
        """
        filename = Path(filename)

        if filename.suffix.lower() == ".usif":
            # Check if it's a container file by reading magic bytes
            try:
                with open(filename, "rb") as f:
                    magic = f.read(7)
                    if magic == b"USIFC\x00\x00":
                        raise StorageError(
                            f"File {filename} is a StructureContainer, not a USIF structure. "
                            f"Use StructureContainer() to open it."
                        )
            except (IOError, FileNotFoundError):
                pass  # Will be caught below

            # Use USIF decoder for .usif files
            from usif.encoder import USIF

            encoder = USIF()
            return encoder.load(filename)
        else:
            # Use MSONable JSON format for other files
            try:
                import json

                with open(filename, "r") as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except (IOError, FileNotFoundError) as e:
                raise StorageError(
                    f"Failed to load structure from {filename}: {e}"
                ) from e

    def __getattr__(self, name: str):
        """Allow access to 'from' as an alias for 'from_source' (since 'from' is a reserved keyword)"""
        if name == "from":
            return self.from_source
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    @classmethod
    def __getattr__(cls, name: str):  # noqa: F811
        """Allow class-level access to 'from' as an alias for 'from_source'"""
        if name == "from":
            return cls.from_source
        raise AttributeError(f"'{cls.__name__}' has no attribute '{name}'")
