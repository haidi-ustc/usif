#!/usr/bin/env python3
"""
USIF Optimizer
Structure optimization utilities
"""

import numpy as np
import logging
from typing import Optional

try:
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer, PointGroupAnalyzer
    PYMATGEN_AVAILABLE = True
except ImportError:
    PYMATGEN_AVAILABLE = False

from usif.enums import StorageMode, StructureType
from usif.exceptions import SymmetryAnalysisError
from usif.structures.structure import USIFStructure
from usif.structures.sites import WyckoffSite, PointGroupSite, AtomSite

logger = logging.getLogger(__name__)

class USIFOptimizer:
    """Performance optimization utilities for USIF"""
    
    @staticmethod
    def optimize_structure(structure: USIFStructure, 
                          tolerance: float = 1e-3) -> USIFStructure:
        """
        Optimize structure for maximum compression
        
        Args:
            structure: Input USIF structure
            tolerance: Symmetry tolerance for grouping
            
        Returns:
            Optimized USIF structure
        """
        if structure.is_periodic():
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
                structure_type=StructureType.PERIODIC,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=structure.lattice_matrix,
                spacegroup=sga.get_space_group_number(),
                wyckoff_sites=wyckoff_sites,
                structure_properties=structure.structure_properties,
                formula=structure.formula
            )
        except Exception as e:
            logger.debug(f"Crystal optimization failed: {e}")
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
                    structure_type=StructureType.MOLECULAR,
                    storage_mode=StorageMode.SYMMETRIC,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    structure_properties=structure.structure_properties,
                    formula=structure.formula
                )
        except Exception as e:
            logger.debug(f"Molecule optimization failed: {e}")
        
        return structure


