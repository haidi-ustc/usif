#!/usr/bin/env python3
"""
USIF v4.0 - Core Functionality Test Suite
Focused testing of essential USIF format features
"""

import numpy as np
import tempfile
import os
import time
import pytest
from pathlib import Path
import json

# Import USIF modules
from usif import (
    USIF, USIFStructure, StructureType, StorageMode, CompressionType,
    StructureConverter, StructureContainer, USIFOptimizer,
    WyckoffSite, PointGroupSite, AtomSite, AtomicProperties, StructureProperties,
    PropertyRegistry, PropertyDefinition, PropertySerializer,ValidationError
)


class TestUSIFCore:
    """Core functionality tests for USIF format"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.encoder = USIF(compression=CompressionType.GZIP)
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_basic_structure_creation(self):
        """Test creating basic crystal and molecular structures"""
        # Crystal structure with symmetric storage
        lattice_si = np.array([
            [5.43, 0.0, 0.0],
            [0.0, 5.43, 0.0],
            [0.0, 0.0, 5.43]
        ])
        
        silicon = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice_si,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(atomic_number=14, multiplicity=8, coords=(0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=-10.8, volume=160.1),
            formula="Si"
        )
        
        assert silicon.formula == "Si"
        assert silicon.num_atoms() == 8
        assert silicon.spacegroup == 227
        assert silicon.structure_properties.energy == -10.8
        
        # Molecular structure with point group symmetry
        water = USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.SYMMETRIC,
            point_group="C2v",
            point_group_sites=[
                PointGroupSite(atomic_number=8, multiplicity=1, coords=(0.0, 0.0, 0.0)),
                PointGroupSite(atomic_number=1, multiplicity=2, coords=(0.757, 0.586, 0.0))
            ],
            structure_properties=StructureProperties(energy=-76.4),
            formula="H2O"
        )
        
        assert water.formula == "H2O"
        assert water.num_atoms() == 3
        assert water.point_group == "C2v"
    
    def test_encoding_decoding_roundtrip(self):
        """Test encoding and decoding structures"""
        # Create test structure
        nacl_atoms = [
            AtomSite(11, (0.0, 0.0, 0.0), AtomicProperties(charge=0.5)),
            AtomSite(17, (0.5, 0.5, 0.5), AtomicProperties(charge=-0.5))
        ]
        
        nacl = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=np.eye(3) * 5.64,
            spacegroup=225,
            atom_sites=nacl_atoms,
            structure_properties=StructureProperties(energy=-10.5, volume=179.4),
            formula="NaCl"
        )
        
        # Encode and decode
        encoded = self.encoder.encode(nacl)
        decoded, _ = self.encoder.decode(encoded)
        
        # Verify round-trip integrity
        assert nacl == decoded
        assert nacl.formula == decoded.formula
        assert nacl.num_atoms() == decoded.num_atoms()
        assert nacl.structure_properties.energy == decoded.structure_properties.energy
        
        # Test different compression types
        for compression in [CompressionType.NONE, CompressionType.GZIP]:
            encoder = USIF(compression=compression)
            encoded_compressed = encoder.encode(nacl)
            decoded_compressed, _ = encoder.decode(encoded_compressed)
            assert nacl == decoded_compressed
    
    def test_property_system(self):
        """Test structure and atomic properties"""
        # Test built-in properties
        structure_props = StructureProperties(
            energy=-15.8,
            stress=(0.1, 0.1, 0.1, 0.0, 0.0, 0.0),
            pressure=0.05,
            volume=45.5,
            custom={"calculator":"VASP"}
#            functional="PBE",
        )
        
        assert structure_props.energy == -15.8
        assert structure_props.custom["calculator"] == "VASP"
        
        # Test atomic properties
        atomic_props = AtomicProperties(
            charge=0.5,
            magmom=2.0,
            force=(0.01, -0.02, 0.03)
        )
        
        assert atomic_props.charge == 0.5
        assert atomic_props.magmom == 2.0
        
        # Test custom properties
        band_gap_prop = PropertyDefinition(
            name="band_gap",
            data_type=float,
            is_per_atom=False,
            description="Electronic band gap",
            units="eV"
        )
        
        PropertyRegistry.register(band_gap_prop)
        
        custom_structure = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.43,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(14, 8, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(
                energy=-10.8,
                custom={"band_gap": 1.12}
            ),
            formula="Si"
        )
        
        encoded = self.encoder.encode(custom_structure)
        decoded, _ = self.encoder.decode(encoded)
        
        assert "band_gap" in decoded.structure_properties.custom
        assert decoded.structure_properties.custom["band_gap"] == 1.12
    
    def test_storage_mode_efficiency(self):
        """Test storage mode efficiency and optimization"""
        lattice = np.array([
            [4.0, 0.0, 0.0],
            [0.0, 4.0, 0.0],
            [0.0, 0.0, 4.0]
        ])
        
        # Symmetric storage (more efficient for symmetric structures)
        diamond_symmetric = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(6, 8, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=-15.8),
            formula="C"
        )
        
        # Full atomic storage (less efficient but more flexible)
        diamond_atomic = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=lattice,
            spacegroup=227,
            atom_sites=[
                AtomSite(6, (0.0, 0.0, 0.0)),
                AtomSite(6, (0.25, 0.25, 0.25))
            ] * 4,  # 8 atoms total
            structure_properties=StructureProperties(energy=-15.8),
            formula="C"
        )
        
        encoded_symmetric = self.encoder.encode(diamond_symmetric)
        encoded_atomic = self.encoder.encode(diamond_atomic)
        
        # Symmetric should be more compact
        assert len(encoded_symmetric) < len(encoded_atomic)
        
        # Test optimization
        optimized = USIFOptimizer.optimize_structure(diamond_atomic)
        assert optimized.storage_mode == StorageMode.SYMMETRIC
    
    def test_file_operations(self):
        """Test saving and loading structures to/from files"""
        # Create test structure
        aluminum = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=np.eye(3) * 4.05,
            spacegroup=225,
            atom_sites=[AtomSite(13, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=-3.7, volume=66.4),
            formula="Al"
        )
        
        # Save to file
        file_path = os.path.join(self.temp_dir, "aluminum.usif")
        self.encoder.save(aluminum, file_path)
        
        # Verify file exists and has content
        assert os.path.exists(file_path)
        assert os.path.getsize(file_path) > 0
        
        # Load from file
        loaded = self.encoder.load(file_path)
        
        # Verify integrity
        assert aluminum == loaded
        assert aluminum.formula == loaded.formula
        assert aluminum.structure_properties.energy == loaded.structure_properties.energy
        
        # Test with different compression
        for compression in [CompressionType.NONE, CompressionType.GZIP]:
            encoder = USIF(compression=compression)
            file_path_compressed = os.path.join(self.temp_dir, f"aluminum_{compression.name}.usif")
            encoder.save(aluminum, file_path_compressed)
            loaded_compressed = encoder.load(file_path_compressed)
            assert aluminum == loaded_compressed
    
    def test_structure_container(self):
        """Test structure container functionality"""
        container_file = os.path.join(self.temp_dir, "test_container.usifc")
        
        # Create container and add structures
        with StructureContainer(container_file, mode='w') as container:
            # Add various test structures
            test_structures = [
                ("silicon", "Si", -10.8, 160.1, "/crystals/elemental"),
                ("aluminum", "Al", -3.7, 66.4, "/crystals/metals"),
                ("water", "H2O", -76.4, None, "/molecules/small"),
            ]
            
            for name, formula, energy, volume, group in test_structures:
                if formula in ["H2O"]:
                    # Molecular structure
                    structure = USIFStructure(
                        structure_type=StructureType.MOLECULAR,
                        storage_mode=StorageMode.FULL_ATOMIC,
                        atom_sites=[
                            AtomSite(8, (0.0, 0.0, 0.0)),
                            AtomSite(1, (0.757, 0.586, 0.0)),
                            AtomSite(1, (-0.757, 0.586, 0.0))
                        ],
                        structure_properties=StructureProperties(energy=energy),
                        formula=formula
                    )
                else:
                    # Crystal structure
                    structure = USIFStructure(
                        structure_type=StructureType.PERIODIC,
                        storage_mode=StorageMode.SYMMETRIC,
                        lattice_matrix=np.eye(3) * (volume ** (1/3) if volume else 5.0),
                        spacegroup=1,
                        wyckoff_sites=[WyckoffSite(1, 1, (0, 0, 0))],
                        structure_properties=StructureProperties(energy=energy, volume=volume),
                        formula=formula
                    )
                
                container.add(structure, name=name, group=group)
            
            assert len(container) == len(test_structures)
            
            # Test grouping
            groups = container.list_groups()
            assert "/crystals/elemental" in groups
            assert "/molecules/small" in groups
            
            # Test statistics
            stats = container.stats()
            assert stats['total_structures'] == len(test_structures)
            assert stats['total_groups'] == len(groups)
        
        # Reopen for reading
        with StructureContainer(container_file, mode='r') as container:
            # Test queries
            carbon_structures = container.query(formula="C")
            assert len(carbon_structures) == 0  # No carbon in our test data
            
            silicon_structures = container.query(formula="Si")
            assert len(silicon_structures) == 1
            
            # Test group access
            elemental_structures = container.get_structures_in_group("/crystals/elemental")
            assert len(elemental_structures) >= 1
    
    def test_performance_benchmarks(self):
        """Test performance with structures of different sizes"""
        test_cases = [
            ("Small", 10),    # Small structure
            ("Medium", 100),  # Medium structure  
            ("Large", 1000),  # Large structure
        ]
        
        print("\nPerformance Benchmarks:")
        print(f"{'Size':<10} {'Atoms':<8} {'Encode (ms)':<12} {'Decode (ms)':<12} {'Size (bytes)':<12}")
        print("-" * 60)
        
        for size_name, num_atoms in test_cases:
            # Create test structure
            atoms = [AtomSite(6, (i*0.1, i*0.1, i*0.1)) for i in range(num_atoms)]
            structure = USIFStructure(
                structure_type=StructureType.MOLECULAR,
                storage_mode=StorageMode.FULL_ATOMIC,
                atom_sites=atoms,
                structure_properties=StructureProperties(energy=-num_atoms * 1.5),
                formula=f"C{num_atoms}"
            )
            
            # Encoding performance
            start_time = time.perf_counter()
            encoded = self.encoder.encode(structure)
            encode_time = (time.perf_counter() - start_time) * 1000
            
            # Decoding performance  
            start_time = time.perf_counter()
            decoded, _ = self.encoder.decode(encoded)
            decode_time = (time.perf_counter() - start_time) * 1000
            
            size_bytes = len(encoded)
            
            print(f"{size_name:<10} {num_atoms:<8} {encode_time:<12.3f} {decode_time:<12.3f} {size_bytes:<12}")
            
            # Verify round-trip
            assert structure.num_atoms() == decoded.num_atoms()
    
    def test_error_handling(self):
        """Test error handling and validation"""
        # Test invalid structure creation
        with pytest.raises(ValidationError):
            # Molecular structure should not have lattice
            USIFStructure(
                structure_type=StructureType.MOLECULAR,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=np.eye(3),
                point_group="C1",
                point_group_sites=[PointGroupSite(1, 1, (0, 0, 0))],
                formula="H"
            )
        
        with pytest.raises(ValidationError):
            # Periodic structure must have lattice
            USIFStructure(
                structure_type=StructureType.PERIODIC,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=None,  # Invalid for periodic
                spacegroup=1,
                wyckoff_sites=[WyckoffSite(1, 1, (0, 0, 0))],
                formula="H"
            )
        
    def test_structure_hashing(self):
        """Test structure hashing for identity and comparison"""
        # Create identical structures
        lattice = np.eye(3) * 5.0
        structure1 = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice,
            spacegroup=1,
            wyckoff_sites=[WyckoffSite(1, 1, (0, 0, 0))],
            formula="H"
        )
        
        structure2 = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice.copy(),  # Different object, same values
            spacegroup=1,
            wyckoff_sites=[WyckoffSite(1, 1, (0, 0, 0))],
            formula="H"
        )
        
        # Should be equal
        assert structure1 == structure2
        
        # Hashes should be equal for equal structures
        hash1 = self.encoder.get_structure_hash(structure1)
        hash2 = self.encoder.get_structure_hash(structure2)
        assert hash1 == hash2
        
        # Different structure should have different hash
        structure3 = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.1,  # Different lattice constant
            spacegroup=1,
            wyckoff_sites=[WyckoffSite(1, 1, (0, 0, 0))],
            formula="H"
        )
        
        hash3 = self.encoder.get_structure_hash(structure3)
        assert hash1 != hash3


def run_comprehensive_test():
    """Run comprehensive test suite"""
    print("USIF v4.0 - Comprehensive Core Test Suite")
    print("=" * 70)
    
    test_suite = TestUSIFCore()
    
    # Run all test methods
    test_methods = [method for method in dir(test_suite) 
                   if method.startswith('test_') and callable(getattr(test_suite, method))]
    
    results = {}
    
    for method_name in test_methods:
        print(f"\nRunning {method_name}...")
        try:
            test_suite.setup_method()
            getattr(test_suite, method_name)()
            results[method_name] = "PASSED"
            print(f"✓ {method_name}: PASSED")
        except Exception as e:
            results[method_name] = f"FAILED: {str(e)}"
            print(f"✗ {method_name}: FAILED - {str(e)}")
        finally:
            test_suite.teardown_method()
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result == "PASSED")
    
    for test, result in results.items():
        status = "✓" if result == "PASSED" else "✗"
        print(f"{status} {test}: {result}")
    
    print(f"\nTotal: {total_tests}, Passed: {passed_tests}, Failed: {total_tests - passed_tests}")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! 🎉")
    else:
        print("❌ SOME TESTS FAILED")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_comprehensive_test()
    exit(0 if success else 1)
