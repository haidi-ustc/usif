#!/usr/bin/env python3
"""
USIF Structure
Universal structure representation for crystals and molecules
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
from pathlib import Path
from monty.json import MSONable

from usif.enums import StructureType, StorageMode, CompressionType
from usif.exceptions import ValidationError, StorageError
from usif.structures.sites import WyckoffSite, PointGroupSite, AtomSite
from usif.properties.structure import StructureProperties
from usif.properties.atomic import AtomicProperties

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
    
    __slots__ = ['structure_type', 'storage_mode', 'lattice_matrix', 'spacegroup', 
                'point_group', 'wyckoff_sites', 'point_group_sites', 'atom_sites',
                'structure_properties', 'formula']
    
    def __init__(self, 
                 structure_type: StructureType = StructureType.CRYSTAL,
                 storage_mode: StorageMode = StorageMode.SYMMETRIC,
                 lattice_matrix: Optional[np.ndarray] = None,
                 spacegroup: int = 1,
                 point_group: Optional[str] = None,
                 wyckoff_sites: Optional[List[WyckoffSite]] = None,
                 point_group_sites: Optional[List[PointGroupSite]] = None,
                 atom_sites: Optional[List[AtomSite]] = None,
                 structure_properties: Optional[StructureProperties] = None,
                 formula: str = ""):
        
        self.structure_type = structure_type
        self.storage_mode = storage_mode
        self.lattice_matrix = lattice_matrix
        self.spacegroup = spacegroup
        self.point_group = point_group
        self.wyckoff_sites = wyckoff_sites
        self.point_group_sites = point_group_sites
        self.atom_sites = atom_sites
        self.structure_properties = structure_properties if structure_properties is not None \
                                    else StructureProperties()
        self.formula = formula
        
        self._validate_structure()
    
    def _validate_structure(self) -> None:
        """Validate structure configuration"""
        if self.structure_type == StructureType.MOLECULE:
            if self.lattice_matrix is not None:
                raise ValidationError("Molecular structures should not have lattice")
            if self.storage_mode == StorageMode.SYMMETRIC:
                if self.point_group_sites is None or len(self.point_group_sites) == 0:
                    raise ValidationError("Molecular SYMMETRIC mode requires non-empty point_group_sites")
            elif self.storage_mode == StorageMode.FULL_ATOMIC:
                if self.atom_sites is None or len(self.atom_sites) == 0:
                    raise ValidationError("Molecular FULL_ATOMIC mode requires non-empty atom_sites")
        else:
            if self.lattice_matrix is None:
                raise ValidationError("Crystal structures require lattice")
            if self.storage_mode == StorageMode.SYMMETRIC:
                if self.wyckoff_sites is None or len(self.wyckoff_sites) == 0:
                    raise ValidationError("Crystal SYMMETRIC mode requires non-empty wyckoff_sites")
            elif self.storage_mode == StorageMode.FULL_ATOMIC:
                if self.atom_sites is None or len(self.atom_sites) == 0:
                    raise ValidationError("Crystal FULL_ATOMIC mode requires non-empty atom_sites")
    
    def is_periodic(self) -> bool:
        """Check if structure is periodic (crystal)"""
        return self.structure_type == StructureType.CRYSTAL
    
    def is_molecular(self) -> bool:
        """Check if structure is molecular"""
        return self.structure_type == StructureType.MOLECULE
    
    def is_symmetric(self) -> bool:
        """Check if using symmetric storage"""
        return self.storage_mode == StorageMode.SYMMETRIC
    
    def num_atoms(self) -> int:
        """Get total number of atoms"""
        if self.storage_mode == StorageMode.SYMMETRIC:
            if self.is_periodic():
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
        
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        d = {
            "@module": self.__class__.__module__,
            "@class": self.__class__.__name__,
            "structure_type": self.structure_type.value,
            "storage_mode": self.storage_mode.value,
            "spacegroup": self.spacegroup,
            "point_group": self.point_group,
            "structure_properties": self.structure_properties,
            "formula": self.formula
        }
        
        if self.lattice_matrix is not None:
            d["lattice_matrix"] = self.lattice_matrix.tolist()
        
        if self.wyckoff_sites is not None:
            d["wyckoff_sites"] = [{
                'atomic_number': site.atomic_number,
                'multiplicity': site.multiplicity,
                'coords': site.coords,
                'occupancy': site.occupancy
            } for site in self.wyckoff_sites]
        
        if self.point_group_sites is not None:
            d["point_group_sites"] = [{
                'atomic_number': site.atomic_number,
                'multiplicity': site.multiplicity,
                'coords': site.coords,
                'occupancy': site.occupancy
            } for site in self.point_group_sites]
        
        if self.atom_sites is not None:
            d["atom_sites"] = [{
                'atomic_number': site.atomic_number,
                'coords': site.coords,
                'properties': {
                    'force': site.properties.force,
                    'charge': site.properties.charge,
                    'magmom': site.properties.magmom,
                    'velocity': site.properties.velocity,
                    'custom': site.properties.custom
                }
            } for site in self.atom_sites]
        
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> 'USIFStructure':
        """
        Create USIFStructure from MSONable dictionary
        
        Args:
            d: Dictionary representation from as_dict()
            
        Returns:
            USIFStructure instance
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
                props_dict = site_dict.get('properties', {})
                atom_props = AtomicProperties(
                    force=props_dict.get('force'),
                    charge=props_dict.get('charge'),
                    magmom=props_dict.get('magmom'),
                    velocity=props_dict.get('velocity'),
                    custom=props_dict.get('custom', {})
                )
                atom_sites.append(AtomSite(
                    atomic_number=site_dict['atomic_number'],
                    coords=site_dict['coords'],
                    properties=atom_props
                ))
        
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
            formula=d["formula"]
        )
    
    def __eq__(self, other):
        if not isinstance(other, USIFStructure):
            return False
        
        lattice_equal = True
        if self.lattice_matrix is not None and other.lattice_matrix is not None:
            lattice_equal = np.allclose(self.lattice_matrix, other.lattice_matrix, atol=1e-6)
        elif self.lattice_matrix != other.lattice_matrix:
            lattice_equal = False
        
        return (self.structure_type == other.structure_type and
                self.storage_mode == other.storage_mode and
                lattice_equal and
                self.spacegroup == other.spacegroup and
                self.point_group == other.point_group and
                self.wyckoff_sites == other.wyckoff_sites and
                self.point_group_sites == other.point_group_sites and
                self.atom_sites == other.atom_sites and
                self.structure_properties == other.structure_properties and
                self.formula == other.formula)
    
    def __repr__(self):
        return (f"USIFStructure(structure_type={self.structure_type.name}, "
                f"storage_mode={self.storage_mode.name}, "
                f"formula='{self.formula}', "
                f"atoms={self.num_atoms()})")
    
    @classmethod
    def from_pymatgen(cls, pmg_obj, 
                     forces: Optional[np.ndarray] = None,
                     stress: Optional[np.ndarray] = None,
                     energy: Optional[float] = None,
                     charges: Optional[np.ndarray] = None,
                     magmoms: Optional[np.ndarray] = None,
                     force_symmetric: bool = False,
                     **kwargs) -> 'USIFStructure':
        """
        Create USIFStructure from pymatgen Structure or Molecule
        
        This is a convenient class method that automatically handles symmetry
        analysis and Wyckoff site extraction from pymatgen objects.
        
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
            **kwargs
        )
    
    def save(self, filename: Union[str, Path], 
             compression: CompressionType = CompressionType.GZIP) -> None:
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
        
        if filename.suffix.lower() == '.usif':
            # Use USIF encoder for .usif files
            from usif.encoder import USIF
            encoder = USIF(compression=compression)
            encoder.save(self, filename)
        else:
            # Use MSONable JSON format for other files
            try:
                import json
                # Use monty.json's jsanitize for proper serialization
                from monty.json import jsanitize
                with open(filename, 'w') as f:
                    json.dump(jsanitize(self.as_dict()), f, indent=2)
            except IOError as e:
                raise StorageError(f"Failed to save structure to {filename}: {e}") from e
    
    @classmethod
    def load(cls, filename: Union[str, Path]) -> 'USIFStructure':
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
        
        if filename.suffix.lower() == '.usif':
            # Use USIF decoder for .usif files
            from usif.encoder import USIF
            encoder = USIF()
            return encoder.load(filename)
        else:
            # Use MSONable JSON format for other files
            try:
                import json
                with open(filename, 'r') as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except (IOError, FileNotFoundError) as e:
                raise StorageError(f"Failed to load structure from {filename}: {e}") from e



