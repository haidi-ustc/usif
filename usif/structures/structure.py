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
    - usif.interop.pymatgen: Convert from/to pymatgen
    - WyckoffSite, PointGroupSite, AtomSite: Site types
    - StructureProperties, AtomicProperties: Property types
"""

from pathlib import Path
from typing import Any, List, Optional, Union

import numpy as np
from monty.json import MSONable

from usif.constants import CompressionType, StorageMode, StructureType
from usif.exceptions import ValidationError
from usif.properties.atomic import AtomicProperties
from usif.properties.structure import StructureProperties
from usif.structures.metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
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

    def set_symmetry_metadata(self, metadata: SymmetryMetadata) -> None:
        """Attach symmetry reconstruction metadata to structure properties."""
        self.structure_properties.custom[SYMMETRY_METADATA_KEY] = metadata.as_dict()

    def get_symmetry_metadata(self) -> Optional[SymmetryMetadata]:
        """Return symmetry reconstruction metadata if present."""
        data = self.structure_properties.custom.get(SYMMETRY_METADATA_KEY)
        if data is None:
            return None
        if isinstance(data, SymmetryMetadata):
            return data
        if isinstance(data, dict):
            return SymmetryMetadata.from_dict(data)
        return None

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

        For crystals: Only includes crystal-related properties (lattice_matrix,
        spacegroup, wyckoff_sites). Molecular properties (point_group,
        point_group_sites) are excluded.

        For molecules: Only includes molecular-related properties (point_group,
        point_group_sites). Crystal properties (lattice_matrix, spacegroup,
        wyckoff_sites) are excluded.

        Returns:
            dict: Dictionary representation with structure-type-specific data

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
            "structure_properties": self.structure_properties,
            "formula": self.formula,
        }

        if self.is_crystal():
            # Crystal-specific properties
            if self.lattice_matrix is not None:
                d["lattice_matrix"] = self.lattice_matrix.tolist()
            d["spacegroup"] = self.spacegroup

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
        else:
            # Molecular-specific properties
            if self.point_group is not None:
                d["point_group"] = self.point_group

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

        # Atom sites are common to both structure types (for FULL_ATOMIC mode)
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

        Handles structure-type-specific properties:
        - For crystals: reads lattice_matrix, spacegroup, wyckoff_sites
        - For molecules: reads point_group, point_group_sites
        - Properties not relevant to the structure type are ignored

        Args:
            d: Dictionary representation from as_dict()

        Returns:
            USIFStructure: Reconstructed structure instance

        Example:
            >>> structure_dict = structure.as_dict()
            >>> reconstructed = USIFStructure.from_dict(structure_dict)
        """
        structure_type = StructureType(d["structure_type"])
        is_crystal = structure_type == StructureType.CRYSTAL

        # Crystal-specific properties
        lattice_matrix = None
        spacegroup = 1  # Default value
        wyckoff_sites = None

        if is_crystal:
            if "lattice_matrix" in d and d["lattice_matrix"] is not None:
                lattice_matrix = np.array(d["lattice_matrix"])
            if "spacegroup" in d:
                spacegroup = d["spacegroup"]
            if "wyckoff_sites" in d and d["wyckoff_sites"] is not None:
                wyckoff_sites = []
                for site_dict in d["wyckoff_sites"]:
                    wyckoff_sites.append(WyckoffSite(**site_dict))

        # Molecular-specific properties
        point_group = None
        point_group_sites = None

        if not is_crystal:
            if "point_group" in d:
                point_group = d["point_group"]
            if "point_group_sites" in d and d["point_group_sites"] is not None:
                point_group_sites = []
                for site_dict in d["point_group_sites"]:
                    point_group_sites.append(PointGroupSite(**site_dict))

        # Common properties (atom_sites for FULL_ATOMIC mode)
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
            structure_type=structure_type,
            storage_mode=StorageMode(d["storage_mode"]),
            lattice_matrix=lattice_matrix,
            spacegroup=spacegroup,
            point_group=point_group,
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
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        **kwargs,
    ) -> "USIFStructure":
        """Create a USIFStructure from a file path, pymatgen object, or ASE Atoms."""
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
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        **kwargs,
    ) -> "USIFStructure":
        """Create USIFStructure from a pymatgen Structure or Molecule."""
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

    def to(
        self,
        filename: Optional[Union[str, Path]] = None,
        fmt: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Convert structure to a supported object or file format."""
        from usif.structures.source import convert_to as _convert_to

        return _convert_to(self, filename=filename, fmt=fmt, **kwargs)

    def save(
        self,
        filename: Union[str, Path],
        compression: CompressionType = CompressionType.GZIP,
    ) -> None:
        """Save structure to USIF binary or MSON JSON based on file extension."""
        from usif.structures.io import save_structure as _save_structure

        _save_structure(self, filename, compression=compression)

    @classmethod
    def load(cls, filename: Union[str, Path]) -> "USIFStructure":
        """Load structure from USIF binary or MSON JSON based on file extension."""
        from usif.structures.io import load_structure as _load_structure

        return _load_structure(cls, filename)

