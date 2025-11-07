#!/usr/bin/env python3
"""
Extended test script to verify additional README.md examples
"""

import sys
import os
import tempfile
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from usif import USIFStructure, StructureConverter
    from usif import WyckoffSite, StructureProperties, StructureType, StorageMode
    from pymatgen.core import Structure, Lattice
    from ase import Atoms
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def test_to_default():
    """Test to() method default behavior"""
    print("Testing to() method default behavior...")
    
    try:
        # Create a simple structure
        lattice_matrix = np.array([
            [5.64, 0.0, 0.0],
            [0.0, 5.64, 0.0],
            [0.0, 0.0, 5.64]
        ])
        
        wyckoff_sites = [
            WyckoffSite(atomic_number=11, multiplicity=4, coords=(0.0, 0.0, 0.0)),
            WyckoffSite(atomic_number=17, multiplicity=4, coords=(0.5, 0.5, 0.5))
        ]
        
        usif_struct = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice_matrix,
            spacegroup=225,
            wyckoff_sites=wyckoff_sites,
            structure_properties=StructureProperties(energy=-10.5),
            formula="NaCl"
        )
        
        # Test default behavior (should return pymatgen)
        pmg_struct2 = usif_struct.to()  # Defaults to pymatgen if no args
        assert pmg_struct2 is not None
        assert hasattr(pmg_struct2, 'formula')
        print("  ✓ to() method default behavior works correctly")
        return True
    except Exception as e:
        print(f"  ✗ to() method default behavior failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_structure_converter_examples():
    """Test StructureConverter examples from README"""
    print("Testing StructureConverter examples...")
    
    try:
        # Create test data
        lattice = Lattice.cubic(5.64)
        species = ["Na", "Cl"]
        coords = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]
        pmg_structure = Structure(lattice, species, coords)
        
        forces_array = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        stress_tensor = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        
        # Test from_pymatgen
        usif_struct = StructureConverter.from_pymatgen(
            pmg_structure,
            energy=-10.5,
            forces=forces_array,
            stress=stress_tensor
        )
        assert usif_struct is not None
        print("  ✓ StructureConverter.from_pymatgen works correctly")
        
        # Test from_ase
        ase_atoms = Atoms('H2O', positions=[[0, 0, 0], [0.95, 0, 0], [0.95, 0.95, 0]])
        forces_h2o = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])  # 3 atoms for H2O
        usif_struct2 = StructureConverter.from_ase(
            ase_atoms,
            energy=-10.5,
            forces=forces_h2o
        )
        assert usif_struct2 is not None
        print("  ✓ StructureConverter.from_ase works correctly")
        
        # Test to_pymatgen
        pmg_back = StructureConverter.to_pymatgen(usif_struct)
        assert pmg_back is not None
        assert hasattr(pmg_back, 'formula')
        print("  ✓ StructureConverter.to_pymatgen works correctly")
        
        # Test to_ase (use the crystal structure, not the molecule)
        ase_back = StructureConverter.to_ase(usif_struct)
        assert ase_back is not None
        assert hasattr(ase_back, 'get_positions')
        print("  ✓ StructureConverter.to_ase works correctly")
        
        return True
    except Exception as e:
        print(f"  ✗ StructureConverter examples failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run extended tests"""
    print("=" * 60)
    print("Testing Extended README.md Examples")
    print("=" * 60)
    print()
    
    results = []
    results.append(("to() default behavior", test_to_default()))
    results.append(("StructureConverter examples", test_structure_converter_examples()))
    
    print()
    print("=" * 60)
    print("Extended Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())

