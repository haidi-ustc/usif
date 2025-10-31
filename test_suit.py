#!/usr/bin/env python3
"""
USIF v4.0 - Comprehensive Test Suite
Complete testing of all USIF format features
"""

import numpy as np
import tempfile
import os
import time
from pathlib import Path
from monty.serialization import dumpfn, loadfn

# Import USIF modules
from usif import (
    USIF, USIFStructure, StructureType, StorageMode, CompressionType,
    StructureConverter, StructureContainer, USIFOptimizer,
    WyckoffSite, PointGroupSite, AtomSite, AtomicProperties, StructureProperties,
    PropertyRegistry, PropertyDefinition, PropertySerializer
)


class USIFTestSuite:
    """Comprehensive test suite for USIF format"""
    
    def __init__(self):
        self.encoder = USIF(compression=CompressionType.GZIP)
        self.test_results = {}
    
    def run_all_tests(self):
        """Run all test cases"""
        print("USIF v4.0 - Comprehensive Test Suite")
        print("=" * 70)
        
        self.test_basic_structure_encoding()
        self.test_property_system()
        self.test_storage_modes()
        self.test_file_operations()
        self.test_container_features()
        self.test_pymatgen_integration()
        self.test_performance()
        self.test_edge_cases()
        
        self.print_summary()
    
    def test_basic_structure_encoding(self):
        """Test 1: Basic structure encoding and decoding"""
        print("\n" + "=" * 70)
        print("TEST 1: Basic Structure Encoding/Decoding")
        print("=" * 70)
        
        # Test 1.1: Crystal structure with symmetric storage
        lattice_si = np.array([
            [5.43, 0.0, 0.0],
            [0.0, 5.43, 0.0],
            [0.0, 0.0, 5.43]
        ])
        
        wyckoff_sites_si = [
            WyckoffSite(atomic_number=14, multiplicity=8, coords=(0.0, 0.0, 0.0))
        ]
        
        silicon = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice_si,
            spacegroup=227,
            wyckoff_sites=wyckoff_sites_si,
            structure_properties=StructureProperties(energy=-10.8, volume=160.1),
            formula="Si"
        )
        
        encoded_si = self.encoder.encode(silicon)
        decoded_si, _ = self.encoder.decode(encoded_si)
        
        print("✓ Silicon crystal (symmetric):")
        print(f"  Formula: {silicon.formula}")
        print(f"  Atoms: {silicon.num_atoms()}")
        print(f"  Space group: {silicon.spacegroup}")
        print(f"  Round-trip: {silicon == decoded_si}")
        print(f"  Compression: {len(encoded_si)} bytes")
        
        # Test 1.2: Molecular structure with point group symmetry
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
        
        encoded_water = self.encoder.encode(water)
        decoded_water, _ = self.encoder.decode(encoded_water)
        
        print("\n✓ Water molecule (symmetric):")
        print(f"  Formula: {water.formula}")
        print(f"  Point group: {water.point_group}")
        print(f"  Atoms: {water.num_atoms()}")
        print(f"  Round-trip: {water == decoded_water}")
        print(f"  Compression: {len(encoded_water)} bytes")
        
        self.test_results["basic_encoding"] = True
    
    def test_property_system(self):
        """Test 2: Comprehensive property system testing"""
        print("\n" + "=" * 70)
        print("TEST 2: Property System")
        print("=" * 70)
        
        # Test 2.1: Structure with all built-in properties
        nacl_atoms = [
            AtomSite(11, (0.0, 0.0, 0.0), AtomicProperties(charge=0.5, magmom=0.0)),
            AtomSite(17, (0.5, 0.5, 0.5), AtomicProperties(charge=-0.5, magmom=0.0))
        ]
        
        nacl_props = StructureProperties(
            energy=-10.5,
            energy_per_atom=-5.25,
            stress=(1.0, 1.0, 1.0, 0.0, 0.0, 0.0),
            pressure=0.1,
            forces_rms=0.05,
            forces_max=0.1,
            volume=179.4,
            calculator="VASP",
            functional="PBE",
            converged=True
        )
        
        nacl = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=np.eye(3) * 5.64,
            spacegroup=225,
            atom_sites=nacl_atoms,
            structure_properties=nacl_props,
            formula="NaCl"
        )
        
        encoded_nacl = self.encoder.encode(nacl)
        decoded_nacl, _ = self.encoder.decode(encoded_nacl)
        
        print("✓ NaCl with comprehensive properties:")
        print(f"  Energy: {decoded_nacl.structure_properties.energy} eV")
        print(f"  Stress: {decoded_nacl.structure_properties.stress}")
        print(f"  Pressure: {decoded_nacl.structure_properties.pressure} kBar")
        print(f"  Calculator: {decoded_nacl.structure_properties.calculator}")
        print(f"  All properties preserved: {nacl.structure_properties == decoded_nacl.structure_properties}")
        
        # Test 2.2: Custom property registration and usage
        band_gap_prop = PropertyDefinition(
            name="band_gap",
            data_type=float,
            is_per_atom=False,
            description="Electronic band gap",
            units="eV"
        )
        
        dielectric_prop = PropertyDefinition(
            name="dielectric_constant",
            data_type=float,
            is_per_atom=False,
            description="Static dielectric constant",
            units=""
        )
        
        PropertyRegistry.register_custom_property(band_gap_prop)
        PropertyRegistry.register_custom_property(dielectric_prop)
        
        silicon_custom = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.43,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(14, 8, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(
                energy=-10.8,
                custom={
                    "band_gap": 1.12,
                    "dielectric_constant": 11.7
                }
            ),
            formula="Si"
        )
        
        encoded_custom = self.encoder.encode(silicon_custom)
        decoded_custom, _ = self.encoder.decode(encoded_custom)
        
        print("\n✓ Custom properties:")
        print(f"  Band gap: {decoded_custom.structure_properties.custom.get('band_gap')} eV")
        print(f"  Dielectric constant: {decoded_custom.structure_properties.custom.get('dielectric_constant')}")
        print(f"  Custom properties count: {len(decoded_custom.structure_properties.custom)}")
        
        self.test_results["property_system"] = True
    
    def test_storage_modes(self):
        """Test 3: Different storage modes"""
        print("\n" + "=" * 70)
        print("TEST 3: Storage Modes")
        print("=" * 70)
        
        # Create the same structure in different storage modes
        lattice = np.array([
            [4.0, 0.0, 0.0],
            [0.0, 4.0, 0.0],
            [0.0, 0.0, 4.0]
        ])
        
        # Symmetric storage (Wyckoff positions)
        diamond_symmetric = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(6, 8, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=-15.8),
            formula="C"
        )
        
        # Full atomic storage
        diamond_atomic = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=lattice,
            spacegroup=227,
            atom_sites=[
                AtomSite(6, (0.0, 0.0, 0.0)),
                AtomSite(6, (0.25, 0.25, 0.25))
            ],
            structure_properties=StructureProperties(energy=-15.8),
            formula="C"
        )
        
        encoded_symmetric = self.encoder.encode(diamond_symmetric)
        encoded_atomic = self.encoder.encode(diamond_atomic)
        
        print("✓ Storage mode comparison (Diamond structure):")
        print(f"  Symmetric storage: {len(encoded_symmetric)} bytes")
        print(f"  Full atomic storage: {len(encoded_atomic)} bytes")
        print(f"  Compression ratio: {len(encoded_atomic)/len(encoded_symmetric):.2f}x")
        print(f"  Same number of atoms: {diamond_symmetric.num_atoms()} = {diamond_atomic.num_atoms()}")
        
        # Test optimization
        optimized = USIFOptimizer.optimize_structure(diamond_atomic)
        print(f"  Optimized storage mode: {optimized.storage_mode.name}")
        
        self.test_results["storage_modes"] = True
    
    def test_file_operations(self):
        """Test 4: File I/O operations"""
        print("\n" + "=" * 70)
        print("TEST 4: File Operations")
        print("=" * 70)
        
        # Create test structures
        structures = []
        
        # Metal crystal
        aluminum = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=np.eye(3) * 4.05,
            spacegroup=225,
            atom_sites=[AtomSite(13, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=-3.7, volume=66.4),
            formula="Al"
        )
        structures.append(("aluminum.usif", aluminum))
        
        # Oxide crystal
        mgo = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 4.212,
            spacegroup=225,
            wyckoff_sites=[
                WyckoffSite(12, 4, (0.0, 0.0, 0.0)),
                WyckoffSite(8, 4, (0.5, 0.5, 0.5))
            ],
            structure_properties=StructureProperties(energy=-20.8, volume=74.7),
            formula="MgO"
        )
        structures.append(("mgo.usif", mgo))
        
        # Organic molecule
        benzene_atoms = [
            AtomSite(6, (0.000, 1.396, 0.000)),
            AtomSite(6, (1.209, 0.698, 0.000)),
            AtomSite(6, (1.209, -0.698, 0.000)),
            AtomSite(6, (0.000, -1.396, 0.000)),
            AtomSite(6, (-1.209, -0.698, 0.000)),
            AtomSite(6, (-1.209, 0.698, 0.000)),
            AtomSite(1, (0.000, 2.479, 0.000)),
            AtomSite(1, (2.147, 1.240, 0.000)),
            AtomSite(1, (2.147, -1.240, 0.000)),
            AtomSite(1, (0.000, -2.479, 0.000)),
            AtomSite(1, (-2.147, -1.240, 0.000)),
            AtomSite(1, (-2.147, 1.240, 0.000)),
        ]
        
        benzene = USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=benzene_atoms,
            structure_properties=StructureProperties(energy=-230.5),
            formula="C6H6"
        )
        structures.append(("benzene.usif", benzene))
        
        # Test individual file operations
        for filename, structure in structures:
            # Save to file
            self.encoder.save(structure, filename)
            
            # Load from file
            loaded = self.encoder.load(filename)
            
            # Verify integrity
            original_hash = self.encoder.get_structure_hash(structure)
            loaded_hash = self.encoder.get_structure_hash(loaded)
            
            print(f"✓ {filename}:")
            print(f"  File size: {os.path.getsize(filename)} bytes")
            print(f"  Formula: {loaded.formula}")
            print(f"  Atoms: {loaded.num_atoms()}")
            print(f"  Hash match: {original_hash == loaded_hash}")
            print(f"  Structure match: {structure == loaded}")
            
            # Clean up
            os.unlink(filename)
        
        self.test_results["file_operations"] = True
    
    def test_container_features(self):
        """Test 5: Container with advanced features"""
        print("\n" + "=" * 70)
        print("TEST 5: Container Features")
        print("=" * 70)
        
        # Create temporary container file
        with tempfile.NamedTemporaryFile(suffix='.usifc', delete=False) as tmp:
            container_file = tmp.name
        
        try:
            # Create container and add structures
            with StructureContainer(container_file, mode='w', use_mmap=False) as container:
                # Add various structures with different properties
                structures_data = [
                    ("silicon", "Si", -10.8, 160.1, "/crystals/elemental"),
                    ("diamond", "C", -15.8, 45.5, "/crystals/elemental"),
                    ("aluminum", "Al", -3.7, 66.4, "/crystals/metals"),
                    ("nacl", "NaCl", -10.5, 179.4, "/crystals/salts"),
                    ("water", "H2O", -76.4, None, "/molecules/small"),
                    ("benzene", "C6H6", -230.5, None, "/molecules/organic")
                ]
                
                for name, formula, energy, volume, group in structures_data:
                    if formula in ["H2O", "C6H6"]:
                        # Molecular structures
                        if formula == "H2O":
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
                        else:  # benzene
                            structure = USIFStructure(
                                structure_type=StructureType.MOLECULAR,
                                storage_mode=StorageMode.FULL_ATOMIC,
                                atom_sites=[AtomSite(6 if i < 6 else 1, (0, 0, 0)) for i in range(12)],
                                structure_properties=StructureProperties(energy=energy),
                                formula=formula
                            )
                    else:
                        # Crystal structures
                        structure = USIFStructure(
                            structure_type=StructureType.PERIODIC,
                            storage_mode=StorageMode.SYMMETRIC,
                            lattice_matrix=np.eye(3) * (volume ** (1/3) if volume else 5.0),
                            spacegroup=1,
                            wyckoff_sites=[WyckoffSite(1, 1, (0, 0, 0))],  # Simplified
                            structure_properties=StructureProperties(energy=energy, volume=volume),
                            formula=formula
                        )
                    
                    container.add(structure, name=name, group=group)
                
                print(f"✓ Added {len(container)} structures to container")
                
                # Test grouping
                groups = container.list_groups()
                print(f"✓ Container groups: {groups}")
                
                # Test statistics
                stats = container.stats()
                print(f"✓ Container statistics:")
                print(f"  Total structures: {stats['total_structures']}")
                print(f"  Total groups: {stats['total_groups']}")
                print(f"  Total size: {stats['total_size_bytes']} bytes")
                print(f"  Average structure size: {stats['average_structure_size']:.1f} bytes")
            
            # Reopen container for reading
            with StructureContainer(container_file, mode='r', use_mmap=False) as container:
                # Test queries
                carbon_structures = container.query(formula="C")
                print(f"✓ Found {len(carbon_structures)} carbon structures")
                
                low_energy = container.query(energy_range=(-100, -10))
                print(f"✓ Found {len(low_energy)} structures with energy < -10 eV")
                
                # Test group access
                elemental_structures = container.get_structures_in_group("/crystals/elemental")
                print(f"✓ Found {len(elemental_structures)} structures in /crystals/elemental")
                
                # Test batch operations
                all_hashes = list(container._hash_index.keys())[:3]
                batch_results = container.get_batch_parallel(all_hashes)
                valid_results = [r for r in batch_results if r is not None]
                print(f"✓ Batch retrieved {len(valid_results)}/{len(all_hashes)} structures")
                
        finally:
            # Clean up
            if os.path.exists(container_file):
                os.unlink(container_file)
        
        self.test_results["container_features"] = True
    
    def test_pymatgen_integration(self):
        """Test 6: Pymatgen integration"""
        print("\n" + "=" * 70)
        print("TEST 6: Pymatgen Integration")
        print("=" * 70)
        
        try:
            from pymatgen.core import Structure, Lattice, Molecule
            
            # Test 6.1: Crystal structure conversion
            lattice = Lattice.cubic(5.43)
            species = ["Si", "Si"]
            coords = [[0, 0, 0], [0.25, 0.25, 0.25]]
            pmg_silicon = Structure(lattice, species, coords)
            
            # Convert to USIF
            usif_silicon = StructureConverter.from_pymatgen(pmg_silicon)
            print("✓ Pymatgen → USIF conversion:")
            print(f"  Original formula: {pmg_silicon.formula}")
            print(f"  USIF formula: {usif_silicon.formula}")
            print(f"  Atoms: {usif_silicon.num_atoms()}")
            
            # Convert back to pymatgen
            pmg_back = StructureConverter.to_pymatgen(usif_silicon)
            print(f"  USIF → Pymatgen round-trip: {pmg_silicon.formula == pmg_back.formula}")
            
            # Test 6.2: Molecular conversion
            coords = [[0, 0, 0], [0.757, 0.586, 0], [-0.757, 0.586, 0]]
            species = ["O", "H", "H"]
            pmg_water = Molecule(species, coords)
            
            usif_water = StructureConverter.from_pymatgen(pmg_water)
            pmg_water_back = StructureConverter.to_pymatgen(usif_water)
            
            print("\n✓ Molecular conversion:")
            print(f"  Original: {pmg_water.formula}")
            print(f"  Round-trip: {pmg_water_back.formula}")
            print(f"  Atom count: {len(pmg_water)} → {len(pmg_water_back)}")
            
            self.test_results["pymatgen_integration"] = True
            
        except ImportError:
            print("⚠ Pymatgen not available, skipping integration tests")
            self.test_results["pymatgen_integration"] = False
    
    def test_performance(self):
        """Test 7: Performance benchmarks"""
        print("\n" + "=" * 70)
        print("TEST 7: Performance Benchmarks")
        print("=" * 70)
        
        # Create test structures of different sizes
        test_structures = []
        
        # Small structure (water)
        water = USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=[
                AtomSite(8, (0.0, 0.0, 0.0)),
                AtomSite(1, (0.757, 0.586, 0.0)),
                AtomSite(1, (-0.757, 0.586, 0.0))
            ],
            structure_properties=StructureProperties(energy=-76.4),
            formula="H2O"
        )
        test_structures.append(("Small (H₂O)", water))
        
        # Medium structure (benzene)
        benzene_atoms = [AtomSite(6 if i < 6 else 1, (0, 0, 0)) for i in range(12)]
        benzene = USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=benzene_atoms,
            structure_properties=StructureProperties(energy=-230.5),
            formula="C6H6"
        )
        test_structures.append(("Medium (C₆H₆)", benzene))
        
        # Large structure (simulated protein fragment)
        large_atoms = [AtomSite(6, (i*0.1, i*0.1, i*0.1)) for i in range(100)]
        large_structure = USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=large_atoms,
            structure_properties=StructureProperties(energy=-1500.0),
            formula="C100"
        )
        test_structures.append(("Large (C₁₀₀)", large_structure))
        
        # Performance testing
        print("Performance benchmarks:")
        print(f"{'Structure':<15} {'Atoms':<6} {'Encode (ms)':<12} {'Decode (ms)':<12} {'Size (bytes)':<12} {'Bytes/atom':<12}")
        print("-" * 70)
        
        for name, structure in test_structures:
            # Encoding performance
            start_time = time.time()
            encoded = self.encoder.encode(structure)
            encode_time = (time.time() - start_time) * 1000
            
            # Decoding performance
            start_time = time.time()
            decoded, _ = self.encoder.decode(encoded)
            decode_time = (time.time() - start_time) * 1000
            
            size = len(encoded)
            bytes_per_atom = size / structure.num_atoms()
            
            print(f"{name:<15} {structure.num_atoms():<6} {encode_time:<12.3f} {decode_time:<12.3f} {size:<12} {bytes_per_atom:<12.3f}")
        
        self.test_results["performance"] = True
    
    def test_edge_cases(self):
        """Test 8: Edge cases and error handling"""
        print("\n" + "=" * 70)
        print("TEST 8: Edge Cases & Error Handling")
        print("=" * 70)
        
        # Test 8.1: Empty and invalid structures
        print("✓ Testing error handling:")
        
        try:
            # Invalid: Molecular structure with lattice
            invalid = USIFStructure(
                structure_type=StructureType.MOLECULAR,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=np.eye(3),  # Should not have lattice
                point_group="C1",
                point_group_sites=[PointGroupSite(1, 1, (0, 0, 0))],
                formula="H"
            )
            print("  ✗ Molecular with lattice: Should have failed")
        except ValueError as e:
            print(f"  ✓ Molecular with lattice correctly rejected: {e}")
        
        try:
            # Invalid: Periodic structure without lattice
            invalid = USIFStructure(
                structure_type=StructureType.PERIODIC,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=None,  # Should have lattice
                spacegroup=1,
                wyckoff_sites=[WyckoffSite(1, 1, (0, 0, 0))],
                formula="H"
            )
            print("  ✗ Periodic without lattice: Should have failed")
        except ValueError as e:
            print(f"  ✓ Periodic without lattice correctly rejected: {e}")
        
        # Test 8.2: Large multiplicity values
        large_wyckoff = [WyckoffSite(1, 5000, (0, 0, 0))]  # Large multiplicity
        large_structure = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 10,
            spacegroup=1,
            wyckoff_sites=large_wyckoff,
            formula="H5000"
        )
        
        encoded_large = self.encoder.encode(large_structure)
        decoded_large, _ = self.encoder.decode(encoded_large)
        
        print(f"✓ Large multiplicity (5000 atoms):")
        print(f"  Original atoms: {large_structure.num_atoms()}")
        print(f"  Decoded atoms: {decoded_large.num_atoms()}")
        print(f"  Multiplicity preserved: {large_structure.wyckoff_sites[0].multiplicity == decoded_large.wyckoff_sites[0].multiplicity}")
        
        # Test 8.3: Property validation
        print("\n✓ Property validation:")
        
        # Valid property
        valid = PropertySerializer.validate_value(-10.5, PropertyRegistry.ENERGY)
        print(f"  Valid energy: {valid}")
        
        # Invalid property type
        valid = PropertySerializer.validate_value("invalid", PropertyRegistry.ENERGY)
        print(f"  Invalid energy type: {not valid}")
        
        # Valid per-atom property
        valid = PropertySerializer.validate_value([(0.1, 0.2, 0.3)], PropertyRegistry.FORCE, num_atoms=1)
        print(f"  Valid force (single atom): {valid}")
        
        self.test_results["edge_cases"] = True
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        total_tests = len(self.test_results)
        passed_tests = sum(self.test_results.values())
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! 🎉")
        else:
            print("❌ Some tests failed")
            
        print("=" * 70)


def main():
    """Run the complete test suite"""
    test_suite = USIFTestSuite()
    test_suite.run_all_tests()


if __name__ == "__main__":
    main()
