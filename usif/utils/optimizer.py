#!/usr/bin/env python3
"""
USIF Optimizer Module

This module provides utilities for optimizing structures to achieve maximum
compression by analyzing symmetry and converting to symmetric storage modes
when beneficial.

Main Class:
    USIFOptimizer: Optimize structures for maximum compression

Features:
    - Automatic symmetry analysis using pymatgen
    - Conversion to symmetric storage mode when beneficial
    - Wyckoff site extraction for crystals
    - Point group analysis for molecules
    - Tolerance control for symmetry detection

Requirements:
    - pymatgen: Required dependency for symmetry analysis

Usage:
    >>> from usif import USIFOptimizer, USIFStructure
    >>> 
    >>> # Create optimizer
    >>> optimizer = USIFOptimizer()
    >>> 
    >>> # Optimize structure (may convert to symmetric mode)
    >>> optimized = optimizer.optimize_structure(structure)
    >>> 
    >>> # With custom tolerance
    >>> optimized = optimizer.optimize_structure(
    ...     structure,
    ...     tolerance=1e-4  # Stricter symmetry tolerance
    ... )
    >>> 
    >>> # Check if optimization changed storage mode
    >>> if optimized.storage_mode != structure.storage_mode:
    ...     print("Storage mode changed during optimization")

Note:
    This module requires pymatgen to be installed as a core dependency.

See Also:
    - USIFStructure: Structure to optimize
    - StructureConverter: Conversion utilities
    - SymmetryConstants: Symmetry tolerance constants
"""

import logging
from collections import defaultdict
from typing import Optional

import numpy as np
from pymatgen.symmetry.analyzer import PointGroupAnalyzer, SpacegroupAnalyzer

from usif.constants import SymmetryConstants
from usif.converter import StructureConverter
from usif.enums import StorageMode, StructureType
from usif.exceptions import SymmetryAnalysisError, ValidationError
from usif.structures.sites import AtomSite, PointGroupSite, WyckoffSite
from usif.structures.structure import USIFStructure

logger = logging.getLogger(__name__)

class USIFOptimizer:
    """Performance optimization utilities for USIF"""
    
    @staticmethod
    def optimize_structure(structure: USIFStructure, 
                          tolerance: float = SymmetryConstants.DEFAULT_SYMMETRY_TOLERANCE) -> USIFStructure:
        """
        Optimize structure for maximum compression
        
        Analyzes structure symmetry and converts to symmetric storage mode if beneficial.
        For crystals, extracts Wyckoff sites. For molecules, extracts point group sites.
        This can significantly reduce file size for symmetric structures.
        
        Args:
            structure: Input USIFStructure to optimize
            tolerance: Symmetry tolerance for grouping atoms (default: 1e-3)
            
        Returns:
            USIFStructure: Optimized structure (may have different storage_mode)
            
        Note:
            Requires pymatgen (core dependency).
            
        Example:
            >>> optimizer = USIFOptimizer()
            >>> # Optimize with default tolerance
            >>> optimized = optimizer.optimize_structure(structure)
            >>> # Optimize with stricter tolerance
            >>> optimized = optimizer.optimize_structure(structure, tolerance=1e-4)
            >>> 
            >>> # Check if storage mode changed
            >>> if optimized.storage_mode != structure.storage_mode:
            ...     print("Converted to symmetric storage mode")
        """
        if structure.is_crystal():
            return USIFOptimizer._optimize_crystal(structure, tolerance)
        else:
            return USIFOptimizer._optimize_molecule(structure, tolerance)
    
    @staticmethod
    def _optimize_crystal(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize crystal structure"""
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure
        
        try:
            pmg_structure = StructureConverter.to_pymatgen(structure)
            
            sga = SpacegroupAnalyzer(pmg_structure, symprec=tolerance)
            symmetrized = sga.get_symmetrized_structure()
            
            wyckoff_sites = []
            for equiv_sites in symmetrized.equivalent_sites:
                rep = equiv_sites[0]
                atomic_num = rep.specie.Z
                wyckoff_sites.append(
                    WyckoffSite(atomic_num, len(equiv_sites), tuple(rep.frac_coords))
                )
            
            return USIFStructure(
                structure_type=StructureType.CRYSTAL,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=structure.lattice_matrix,
                spacegroup=sga.get_space_group_number(),
                wyckoff_sites=wyckoff_sites,
                structure_properties=structure.structure_properties,
                formula=structure.formula
            )
        except (ValueError, RuntimeError) as e:
            logger.debug(f"Crystal optimization failed due to symmetry analysis error: {e}")
            return structure
        except ValidationError as e:
            logger.warning(f"Crystal optimization failed due to validation error: {e}")
            return structure
        except Exception as e:
            logger.error(f"Unexpected error during crystal optimization: {e}", exc_info=True)
            return structure
    
    @staticmethod
    def _optimize_molecule(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize molecular structure"""
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure
        
        try:
            pmg_molecule = StructureConverter.to_pymatgen(structure)
            
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
                        
                        if min_dist < tolerance:
                            equiv_count += 1
                            used.add(other_idx)
                    
                    point_group_sites.append(
                        PointGroupSite(atomic_num, equiv_count, tuple(coords))
                    )
            
            total_multiplicity = sum(s.multiplicity for s in point_group_sites)
            if total_multiplicity == len(pmg_molecule) and \
               len(point_group_sites) < len(pmg_molecule):
                return USIFStructure(
                    structure_type=StructureType.MOLECULE,
                    storage_mode=StorageMode.SYMMETRIC,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    structure_properties=structure.structure_properties,
                    formula=structure.formula
                )
        except (ValueError, RuntimeError) as e:
            logger.debug(f"Molecule optimization failed due to symmetry analysis error: {e}")
        except ValidationError as e:
            logger.warning(f"Molecule optimization failed due to validation error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during molecule optimization: {e}", exc_info=True)
        
        return structure


