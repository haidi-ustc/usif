#!/usr/bin/env python3
"""
USIF Structure Converter Module

This module provides conversion utilities between USIF and pymatgen formats.
It handles automatic symmetry analysis and Wyckoff site extraction.

Main Class:
    StructureConverter: Convert between USIF and pymatgen structures

Features:
    - Convert pymatgen Structure/Molecule to USIF
    - Automatic symmetry analysis and Wyckoff site extraction
    - Support for properties (forces, stress, energy, charges, magmoms)
    - Automatic storage mode selection (symmetric vs full atomic)

Requirements:
    - pymatgen: Required for conversion functionality
    - Install with: pip install pymatgen

Usage:
    >>> from pymatgen.core import Structure
    >>> from usif import StructureConverter
    >>> 
    >>> # Load pymatgen structure
    >>> pmg_struct = Structure.from_file('structure.cif')
    >>> 
    >>> # Convert to USIF with properties
    >>> usif_struct = StructureConverter.from_pymatgen(
    ...     pmg_struct,
    ...     energy=-10.5,
    ...     forces=forces_array,
    ...     stress=stress_tensor
    ... )
    >>> 
    >>> # Or use the convenience method
    >>> from usif import USIFStructure
    >>> usif_struct = USIFStructure.from_pymatgen(pmg_struct, energy=-10.5)

Note:
    This module requires pymatgen as a core dependency.

See Also:
    - USIFStructure.from_pymatgen(): Convenience method for conversion
    - pymatgen: https://pymatgen.org/
"""

import numpy as np
from typing import Optional, Dict, Any, Union
from pathlib import Path
from collections import defaultdict
import logging

from pymatgen.core import Structure as PMGStructure, Lattice, Element
from pymatgen.core import Molecule as PMGMolecule
from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar, Vasprun
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer, PointGroupAnalyzer

from usif.enums import StructureType, StorageMode
from usif.exceptions import SymmetryAnalysisError, ValidationError
from usif.constants import SymmetryConstants
from usif.structures.structure import USIFStructure
from usif.structures.sites import WyckoffSite, PointGroupSite, AtomSite
from usif.properties.structure import StructureProperties
from usif.properties.atomic import AtomicProperties

logger = logging.getLogger(__name__)

class StructureConverter:
    """Conversion between USIF and pymatgen"""
    
    @staticmethod
    def from_pymatgen(pmg_obj: Union[PMGStructure, PMGMolecule],
                     forces: Optional[np.ndarray] = None,
                     stress: Optional[np.ndarray] = None,
                     energy: Optional[float] = None,
                     charges: Optional[np.ndarray] = None,
                     magmoms: Optional[np.ndarray] = None,
                     force_symmetric: bool = False,
                     **kwargs) -> USIFStructure:
        """
        Convert pymatgen Structure or Molecule to USIF format
        
        Automatically performs symmetry analysis and extracts Wyckoff sites
        for crystals or point group sites for molecules. Handles both
        symmetric and full atomic storage modes based on properties.
        
        Args:
            pmg_obj: Pymatgen Structure or Molecule object
            forces: Optional forces array (Nx3 for N atoms, in eV/Å)
            stress: Optional stress tensor (3x3 or 6-element Voigt notation, in GPa)
            energy: Optional total energy (in eV)
            charges: Optional atomic charges array (N elements, in e)
            magmoms: Optional magnetic moments array (N elements, in μB)
            force_symmetric: Force symmetric storage mode (default: auto-detect)
            **kwargs: Additional properties to store in structure_properties.custom
            
        Returns:
            USIFStructure: Converted structure with properties
            
        Raises:
            SymmetryAnalysisError: If symmetry analysis fails
            ValidationError: If input data is invalid
            
        Example:
            >>> from pymatgen.core import Structure
            >>> pmg_struct = Structure.from_file("structure.cif")
            >>> usif_struct = StructureConverter.from_pymatgen(
            ...     pmg_struct,
            ...     energy=-10.5,
            ...     forces=forces_array,
            ...     stress=stress_tensor
            ... )
        """
        is_molecule = isinstance(pmg_obj, PMGMolecule)
        
        if is_molecule:
            return StructureConverter._from_molecule(
                pmg_obj, forces, charges, energy, force_symmetric, **kwargs
            )
        else:
            return StructureConverter._from_crystal(
                pmg_obj, forces, stress, energy, charges, magmoms, force_symmetric, **kwargs
            )
    
    @staticmethod
    def _from_molecule(pmg_molecule: PMGMolecule,
                      forces: Optional[np.ndarray] = None,
                      charges: Optional[np.ndarray] = None,
                      energy: Optional[float] = None,
                      force_symmetric: bool = False,
                      **kwargs) -> USIFStructure:
        """Convert pymatgen Molecule to USIF"""
        has_atomic_properties = forces is not None or charges is not None
        
        if force_symmetric or (not has_atomic_properties):
            try:
                pga = PointGroupAnalyzer(pmg_molecule)
                point_group = pga.sch_symbol
                
                atom_groups = defaultdict(list)
                
                for i, site in enumerate(pmg_molecule):
                    atomic_num = site.specie.Z
                    atom_groups[atomic_num].append((i, np.array(site.coords)))
                
                point_group_sites = []
                used = set()
                
                for atomic_num, atoms in atom_groups.items():
                    for idx, coords in atoms:
                        if idx in used:
                            continue
                        
                        equiv_count = 1
                        used.add(idx)
                        
                        for other_idx, other_coords in atoms:
                            if other_idx in used:
                                continue
                            
                            min_dist = float('inf')
                            for sym_op in pga.get_symmetry_operations():
                                transformed = sym_op.operate(coords)
                                dist = np.linalg.norm(transformed - other_coords)
                                min_dist = min(min_dist, dist)
                            
                            if min_dist < SymmetryConstants.MOLECULAR_EQUIVALENCE_THRESHOLD:
                                equiv_count += 1
                                used.add(other_idx)
                        
                        point_group_sites.append(
                            PointGroupSite(atomic_num, equiv_count, tuple(coords))
                        )
                
                total_multiplicity = sum(s.multiplicity for s in point_group_sites)
                if total_multiplicity == len(pmg_molecule) and \
                   len(point_group_sites) < len(pmg_molecule):
                    struct_props = StructureProperties()
                    if energy is not None:
                        struct_props.energy = energy
                    # Add any custom properties from kwargs
                    if kwargs:
                        struct_props.custom.update(kwargs)
                    
                    formula = pmg_molecule.composition.reduced_formula
                    
                    return USIFStructure(
                        structure_type=StructureType.MOLECULE,
                        storage_mode=StorageMode.SYMMETRIC,
                        point_group=point_group,
                        point_group_sites=point_group_sites,
                        structure_properties=struct_props,
                        formula=formula
                    )
            except (ValueError, RuntimeError) as e:
                logger.debug(f"Symmetric molecule conversion failed due to symmetry analysis error: {e}")
            except ValidationError as e:
                logger.warning(f"Symmetric molecule conversion failed due to validation error: {e}")
        
        atom_sites = []
        for i, site in enumerate(pmg_molecule):
            atomic_num = site.specie.Z
            
            atom_props = AtomicProperties()
            if forces is not None and i < len(forces):
                atom_props.force = tuple(forces[i])
            if charges is not None and i < len(charges):
                atom_props.charge = float(charges[i])
            
            atom_sites.append(AtomSite(atomic_num, tuple(site.coords), atom_props))
        
        struct_props = StructureProperties()
        if energy is not None:
            struct_props.energy = energy
        # Add any custom properties from kwargs
        if kwargs:
            struct_props.custom.update(kwargs)
        
        formula = pmg_molecule.composition.reduced_formula
        
        return USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=atom_sites,
            structure_properties=struct_props,
            formula=formula
        )
    
    @staticmethod
    def _from_crystal(pmg_structure: PMGStructure,
                     forces: Optional[np.ndarray] = None,
                     stress: Optional[np.ndarray] = None,
                     energy: Optional[float] = None,
                     charges: Optional[np.ndarray] = None,
                     magmoms: Optional[np.ndarray] = None,
                     force_symmetric: bool = False,
                     **kwargs) -> USIFStructure:
        """Convert pymatgen Structure to USIF"""
        lattice_matrix = pmg_structure.lattice.matrix.copy()
        
        has_atomic_properties = (
            forces is not None or charges is not None or magmoms is not None
        )
        
        if force_symmetric:
            storage_mode = StorageMode.SYMMETRIC
        else:
            storage_mode = StorageMode.FULL_ATOMIC if has_atomic_properties else StorageMode.SYMMETRIC
        
        wyckoff_sites = None
        atom_sites = None
        spacegroup_number = 1
        
        if storage_mode == StorageMode.SYMMETRIC:
            try:
                sga = SpacegroupAnalyzer(pmg_structure, symprec=SymmetryConstants.DEFAULT_SYMMETRY_PRECISION)
                spacegroup_number = sga.get_space_group_number()
                symmetrized = sga.get_symmetrized_structure()
                
                wyckoff_sites = []
                for equiv_sites in symmetrized.equivalent_sites:
                    rep = equiv_sites[0]
                    atomic_num = rep.specie.Z
                    wyckoff_sites.append(
                        WyckoffSite(atomic_num, len(equiv_sites), tuple(rep.frac_coords))
                    )
            except ValueError as e:
                logger.warning(f"Symmetry analysis failed, using full atomic: {e}")
                storage_mode = StorageMode.FULL_ATOMIC
            except RuntimeError as e:
                logger.error(f"Runtime error in symmetry analysis: {e}")
                storage_mode = StorageMode.FULL_ATOMIC
        
        if storage_mode == StorageMode.FULL_ATOMIC:
            try:
                sga = SpacegroupAnalyzer(pmg_structure, symprec=SymmetryConstants.DEFAULT_SYMMETRY_PRECISION)
                spacegroup_number = sga.get_space_group_number()
            except (ValueError, RuntimeError) as e:
                logger.warning(f"Failed to determine spacegroup: {e}")
                spacegroup_number = 1
            
            atom_sites = []
            for i, site in enumerate(pmg_structure):
                atomic_num = site.specie.Z
                
                atom_props = AtomicProperties()
                if forces is not None and i < len(forces):
                    atom_props.force = tuple(forces[i])
                if charges is not None and i < len(charges):
                    atom_props.charge = float(charges[i])
                if magmoms is not None and i < len(magmoms):
                    atom_props.magmom = float(magmoms[i])
                
                atom_sites.append(AtomSite(atomic_num, tuple(site.frac_coords), atom_props))
        
        struct_props = StructureProperties()
        
        if energy is not None:
            struct_props.energy = energy
        
        if stress is not None:
            if stress.shape == (3, 3):
                struct_props.stress = (
                    stress[0, 0], stress[1, 1], stress[2, 2],
                    stress[0, 1], stress[1, 2], stress[0, 2]
                )
            else:
                struct_props.stress = tuple(stress[:6])
        
        # Set volume - use provided volume if given, otherwise use pymatgen structure volume
        if 'volume' in kwargs:
            struct_props.volume = kwargs.pop('volume')
        else:
            struct_props.volume = pmg_structure.volume
        
        # Add any remaining custom properties from kwargs
        # (built-in properties like energy, stress, volume are handled above)
        if kwargs:
            struct_props.custom.update(kwargs)
        
        formula = pmg_structure.composition.reduced_formula
        
        return USIFStructure(
            structure_type=StructureType.CRYSTAL,
            lattice_matrix=lattice_matrix,
            spacegroup=spacegroup_number,
            storage_mode=storage_mode,
            wyckoff_sites=wyckoff_sites,
            atom_sites=atom_sites,
            structure_properties=struct_props,
            formula=formula
        )
    
    @staticmethod
    def to_pymatgen(usif_structure: USIFStructure) -> Union[PMGStructure, PMGMolecule]:
        """
        Convert USIFStructure to pymatgen format
        
        Converts a USIFStructure back to a pymatgen Structure or Molecule object.
        Expands symmetric sites (Wyckoff or point group) to explicit atomic positions.
        Preserves atomic properties (forces, charges, magmoms) if available.
        
        Args:
            usif_structure: USIFStructure to convert
            
        Returns:
            Union[PMGStructure, PMGMolecule]: Pymatgen Structure or Molecule
            
        Raises:
            ImportError: If pymatgen is not installed
            ValidationError: If structure data is invalid
            
        Example:
            >>> from usif import StructureConverter
            >>> pmg_struct = StructureConverter.to_pymatgen(usif_structure)
            >>> pmg_struct.to("cif", "output.cif")
        """
        if usif_structure.is_molecular():
            return StructureConverter._to_molecule(usif_structure)
        else:
            return StructureConverter._to_crystal(usif_structure)
    
    @staticmethod
    def _to_molecule(usif_structure: USIFStructure) -> PMGMolecule:
        """Convert USIF to pymatgen Molecule"""
        species = []
        coords = []
        site_properties = {}
        
        forces = []
        charges = []
        
        if usif_structure.storage_mode == StorageMode.SYMMETRIC:
            for site in usif_structure.point_group_sites:
                element = Element.from_Z(site.atomic_number)
                for _ in range(site.multiplicity):
                    species.append(element)
                    coords.append(site.coords)
        else:
            for atom in usif_structure.atom_sites:
                element = Element.from_Z(atom.atomic_number)
                species.append(element)
                coords.append(atom.coords)
                
                if atom.properties.force is not None:
                    forces.append(atom.properties.force)
                if atom.properties.charge is not None:
                    charges.append(atom.properties.charge)
        
        if forces:
            site_properties['forces'] = forces
        if charges:
            site_properties['charges'] = charges
        
        return PMGMolecule(species, coords, 
                          site_properties=site_properties if site_properties else None)
    
    @staticmethod
    def _to_crystal(usif_structure: USIFStructure) -> PMGStructure:
        """Convert USIF to pymatgen Structure"""
        lattice_matrix = usif_structure.lattice_matrix
        lattice = Lattice(lattice_matrix)
        
        species = []
        coords = []
        site_properties = {}
        
        if usif_structure.storage_mode == StorageMode.SYMMETRIC:
            for site in usif_structure.wyckoff_sites:
                element = Element.from_Z(site.atomic_number)
                for _ in range(site.multiplicity):
                    species.append(element)
                    coords.append(site.coords)
        else:
            forces = []
            charges = []
            magmoms = []
            
            for site in usif_structure.atom_sites:
                element = Element.from_Z(site.atomic_number)
                species.append(element)
                coords.append(site.coords)
                
                if site.properties.force is not None:
                    forces.append(site.properties.force)
                if site.properties.charge is not None:
                    charges.append(site.properties.charge)
                if site.properties.magmom is not None:
                    magmoms.append(site.properties.magmom)
            
            if forces:
                site_properties['forces'] = forces
            if charges:
                site_properties['charges'] = charges
            if magmoms:
                site_properties['magmoms'] = magmoms
        
        return PMGStructure(
            lattice, species, coords, coords_are_cartesian=False,
            site_properties=site_properties if site_properties else None
        )

