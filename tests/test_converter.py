#!/usr/bin/env python3
"""
Tests for USIF StructureConverter
Test conversion between USIF and pymatgen formats
"""

import unittest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from usif import StructureConverter, USIFStructure, StructureType, StorageMode
from usif.exceptions import SymmetryAnalysisError

from pymatgen.core import Structure, Lattice, Molecule
class TestStructureConverter(unittest.TestCase):
    """Test StructureConverter class"""
    
    def test_from_pymatgen_structure(self):
        """Test converting from pymatgen Structure"""
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        usif_structure = StructureConverter.from_pymatgen(structure)
        self.assertIsInstance(usif_structure, USIFStructure)
        self.assertTrue(usif_structure.is_crystal())
        self.assertEqual(usif_structure.num_atoms(), 2)
    
    def test_from_pymatgen_molecule(self):
        """Test converting from pymatgen Molecule"""
        coords = [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]]
        molecule = Molecule(["O", "H", "H"], coords)
        
        usif_structure = StructureConverter.from_pymatgen(molecule)
        self.assertIsInstance(usif_structure, USIFStructure)
        self.assertTrue(usif_structure.is_molecular())
        self.assertEqual(usif_structure.num_atoms(), 3)
    
    def test_from_pymatgen_with_properties(self):
        """Test converting with properties"""
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        forces = np.array([[0.1, 0.2, 0.3]])
        energy = -10.5
        
        usif_structure = StructureConverter.from_pymatgen(
            structure,
            forces=forces,
            energy=energy,
            calculator="VASP"
        )
        self.assertAlmostEqual(usif_structure.structure_properties.energy, energy, places=5)
        self.assertIn('calculator', usif_structure.structure_properties.custom)
    
    def test_to_pymatgen_structure(self):
        """Test converting to pymatgen Structure"""
        from usif import WyckoffSite, StructureProperties
        import numpy as np
        
        lattice_matrix = np.eye(3) * 5.0
        wyckoff_sites = [WyckoffSite(14, 2, (0.0, 0.0, 0.0))]
        
        usif_structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice_matrix,
            spacegroup=227,
            wyckoff_sites=wyckoff_sites,
            formula="Si"
        )
        
        pmg_structure = StructureConverter.to_pymatgen(usif_structure)
        self.assertIsInstance(pmg_structure, Structure)
        self.assertEqual(len(pmg_structure), 2)
    
    def test_to_pymatgen_molecule(self):
        """Test converting to pymatgen Molecule"""
        from usif import AtomSite, AtomicProperties
        
        atom_sites = [
            AtomSite(8, (0.0, 0.0, 0.0)),
            AtomSite(1, (0.76, 0.59, 0.0)),
            AtomSite(1, (-0.76, 0.59, 0.0))
        ]
        
        usif_structure = USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=atom_sites,
            formula="H2O"
        )
        
        pmg_molecule = StructureConverter.to_pymatgen(usif_structure)
        self.assertIsInstance(pmg_molecule, Molecule)
        self.assertEqual(len(pmg_molecule), 3)
    
    def test_roundtrip_structure(self):
        """Test roundtrip conversion for structure"""
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        usif_structure = StructureConverter.from_pymatgen(structure)
        pmg_structure = StructureConverter.to_pymatgen(usif_structure)
        
        self.assertEqual(len(structure), len(pmg_structure))
        self.assertAlmostEqual(structure.volume, pmg_structure.volume, places=3)
    
    def test_roundtrip_molecule(self):
        """Test roundtrip conversion for molecule"""
        coords = [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]]
        molecule = Molecule(["O", "H", "H"], coords)
        
        usif_structure = StructureConverter.from_pymatgen(molecule)
        pmg_molecule = StructureConverter.to_pymatgen(usif_structure)
        
        self.assertEqual(len(molecule), len(pmg_molecule))


if __name__ == '__main__':
    unittest.main()

