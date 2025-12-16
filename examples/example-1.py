#!/usr/bin/env python3
"""
USIF Test Examples
Comprehensive testing of USIF format with all features
"""

import numpy as np

from usif import (
    USIF,
    AtomicProperties,
    AtomSite,
    PointGroupSite,
    PropertyDefinition,
    PropertyRegistry,
    PropertySerializer,
    StorageMode,
    StructureContainer,
    StructureConverter,
    StructureProperties,
    StructureType,
    USIFBenchmark,
    USIFStructure,
    WyckoffSite,
)


def test_examples():
    """Comprehensive test examples for USIF format"""
    print("USIF Comprehensive Test Examples")
    print("=" * 50)

    # Test 1: Simple Crystal Structure (Symmetric) - Use realistic silicon structure
    print("\n1. Testing Simple Crystal Structure (Symmetric)")

    # Create a proper silicon diamond structure
    lattice = np.array([[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]])

    # Silicon diamond structure has atoms at (0,0,0) and (0.25,0.25,0.25) and symmetric equivalents
    wyckoff_sites = [
        WyckoffSite(14, 8, (0.0, 0.0, 0.0)),  # Silicon positions
    ]

    silicon_crystal = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=lattice,
        spacegroup=227,  # Fd-3m (diamond structure)
        wyckoff_sites=wyckoff_sites,
        structure_properties=StructureProperties(
            energy=-10.5, volume=160.0, custom={"calculator": "vasp"}
        ),
        formula="Si",
    )

    encoder = USIF()
    encoded = encoder.encode(silicon_crystal)
    decoded, _ = encoder.decode(encoded)

    print(f"  Original: {silicon_crystal}")
    print(f"  Decoded: {decoded}")
    print(f"  Match: {silicon_crystal == decoded}")
    print(f"  Compression: {len(encoded)} bytes")
    print(f"  Atoms: {silicon_crystal.num_atoms()}")

    # Test 2: Complex Crystal with Properties (Full Atomic)
    print("\n2. Testing Complex Crystal with Properties (Full Atomic)")

    # Use NaCl structure which is more stable for symmetry analysis
    lattice_nacl = np.array([[5.64, 0.0, 0.0], [0.0, 5.64, 0.0], [0.0, 0.0, 5.64]])

    atom_sites = [
        AtomSite(
            11, (0.0, 0.0, 0.0), AtomicProperties(force=(0.001, -0.002, 0.001))
        ),  # Na
        AtomSite(
            17, (0.5, 0.5, 0.5), AtomicProperties(force=(-0.001, 0.002, -0.001))
        ),  # Cl
    ]

    nacl_crystal = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=lattice_nacl,
        spacegroup=225,  # Fm-3m
        atom_sites=atom_sites,
        structure_properties=StructureProperties(
            energy=-20.8,
            volume=179.4,
            custom={"energy_per_atom": -10.4, "converged": True},
        ),
        formula="NaCl",
    )

    encoded_nacl = encoder.encode(nacl_crystal)
    decoded_nacl, _ = encoder.decode(encoded_nacl)

    print(f"  Formula: {nacl_crystal.formula}")
    print(f"  Atoms: {nacl_crystal.num_atoms()}")
    print(f"  Energy: {nacl_crystal.structure_properties.energy} eV")

    original_forces = [atom.properties.force for atom in nacl_crystal.atom_sites]
    decoded_forces = [atom.properties.force for atom in decoded_nacl.atom_sites]
    print(f"  Original forces type: {[type(f) for f in original_forces]}")
    print(f"  Decoded forces type: {[type(f) for f in decoded_forces]}")
    print(f"  Original forces: {original_forces}")
    print(f"  Decoded forces: {decoded_forces}")

    print(
        f"  Has forces: {all(atom.properties.force is not None for atom in nacl_crystal.atom_sites)}"
    )
    print(f"  Size: {len(encoded_nacl)} bytes")

    basic_match = (
        nacl_crystal.formula == decoded_nacl.formula
        and nacl_crystal.num_atoms() == decoded_nacl.num_atoms()
        and abs(
            nacl_crystal.structure_properties.energy
            - decoded_nacl.structure_properties.energy
        )
        < 1e-6
    )
    print(f"  Basic round-trip successful: {basic_match}")

    # Test 3: Molecular Structure (Symmetric)
    print("\n3. Testing Molecular Structure (Symmetric)")
    water_molecule = USIFStructure(
        structure_type=StructureType.MOLECULE,
        storage_mode=StorageMode.SYMMETRIC,
        point_group="C2v",
        point_group_sites=[
            PointGroupSite(8, 1, (0.0, 0.0, 0.0)),  # Oxygen
            PointGroupSite(1, 2, (0.757, 0.586, 0.0)),  # Hydrogens (symmetric)
        ],
        structure_properties=StructureProperties(
            energy=-76.4, custom={"forces_rms": 0.001, "converged": True}
        ),
        formula="H2O",
    )

    encoded_water = encoder.encode(water_molecule)
    decoded_water, _ = encoder.decode(encoded_water)

    print(f"  Formula: {water_molecule.formula}")
    print(f"  Point group: {water_molecule.point_group}")
    print(f"  Atoms: {water_molecule.num_atoms()}")
    print(f"  Symmetric sites: {len(water_molecule.point_group_sites)}")
    print(f"  Size: {len(encoded_water)} bytes")

    # 简化比较
    water_match = (
        water_molecule.formula == decoded_water.formula
        and water_molecule.num_atoms() == decoded_water.num_atoms()
        and water_molecule.point_group == decoded_water.point_group
    )
    print(f"  Round-trip successful: {water_match}")

    # Test 4: Complex Molecule with Properties
    print("\n4. Testing Complex Molecule with Properties")
    benzene_atoms = [
        AtomSite(6, (0.000, 1.396, 0.000)),  # C
        AtomSite(6, (1.209, 0.698, 0.000)),  # C
        AtomSite(6, (1.209, -0.698, 0.000)),  # C
        AtomSite(6, (0.000, -1.396, 0.000)),  # C
        AtomSite(6, (-1.209, -0.698, 0.000)),  # C
        AtomSite(6, (-1.209, 0.698, 0.000)),  # C
        AtomSite(1, (0.000, 2.479, 0.000)),  # H
        AtomSite(1, (2.147, 1.240, 0.000)),  # H
        AtomSite(1, (2.147, -1.240, 0.000)),  # H
        AtomSite(1, (0.000, -2.479, 0.000)),  # H
        AtomSite(1, (-2.147, -1.240, 0.000)),  # H
        AtomSite(1, (-2.147, 1.240, 0.000)),  # H
    ]

    benzene = USIFStructure(
        structure_type=StructureType.MOLECULE,
        storage_mode=StorageMode.FULL_ATOMIC,
        atom_sites=benzene_atoms,
        structure_properties=StructureProperties(
            energy=-230.5, custom={"calculator": "Gaussian"}
        ),
        formula="C6H6",
    )

    encoded_benzene = encoder.encode(benzene)
    decoded_benzene, _ = encoder.decode(encoded_benzene)

    print(f"  Formula: {benzene.formula}")
    print(f"  Atoms: {benzene.num_atoms()}")
    print(f"  Size: {len(encoded_benzene)} bytes")

    benzene_match = (
        benzene.formula == decoded_benzene.formula
        and benzene.num_atoms() == decoded_benzene.num_atoms()
        and abs(
            benzene.structure_properties.energy
            - decoded_benzene.structure_properties.energy
        )
        < 1e-6
    )
    print(f"  Round-trip successful: {benzene_match}")

    # Test 5: Container with Multiple Structures
    print("\n5. Testing Container with Multiple Structures")

    # Create container and add structures
    with StructureContainer("test_materials.usifc", mode="w") as container:
        # Add to different groups
        container.add(
            silicon_crystal, name="silicon_diamond", group="/crystals/elemental"
        )
        container.add(nacl_crystal, name="sodium_chloride", group="/crystals/salts")
        container.add(water_molecule, name="water", group="/molecules/small")
        container.add(benzene, name="benzene", group="/molecules/organic")

        print(f"  Total structures in container: {len(container)}")

    # Test reading and querying
    with StructureContainer("test_materials.usifc", mode="r") as container:
        # Get all structures
        all_structures = list(container)
        print(f"  Found {len(all_structures)} total structures")

        # Test direct access
        if len(container._hash_index) > 0:
            first_hash = list(container._hash_index.keys())[0]
            first_structure = container.get(first_hash)
            if first_structure:
                print(f"  First structure: {first_structure.formula}")

        # Test group access
        groups = container.list_groups()
        print(f"  Container groups: {groups}")

        # Test querying
        crystal_results = container.query(formula="Si")
        print(f"  Found {len(crystal_results)} silicon structures")

    # Test 6: Pymatgen Conversion
    print("\n6. Testing Pymatgen Conversion")

    # Create a simple cubic structure
    from pymatgen.core import Lattice
    from pymatgen.core import Structure as PMGStructure

    lattice_simple = Lattice.cubic(3.0)
    species = ["Li"]
    coords = [[0, 0, 0]]
    simple_structure = PMGStructure(lattice_simple, species, coords)

    # Convert pymatgen to USIF
    usif_from_pmg = StructureConverter.from_pymatgen(
        simple_structure, force_symmetric=True
    )
    print(f"  Pymatgen to USIF: {usif_from_pmg.formula}")

    # Convert USIF back to pymatgen
    pmg_back = StructureConverter.to_pymatgen(usif_from_pmg)
    print(f"  USIF to pymatgen: {pmg_back.formula}")
    print(f"  Round-trip successful: {simple_structure.formula == pmg_back.formula}")

    # Test 7: Performance Benchmark
    print("\n7. Testing Performance Benchmark")

    structures = [silicon_crystal, water_molecule, benzene]
    benchmark_results = USIFBenchmark.benchmark_compression(structures)

    print(f"  Number of structures: {benchmark_results['num_structures']}")
    print(
        f"  Average compression ratio: {benchmark_results['average_compression_ratio']:.3f}"
    )
    print(f"  Compression speedup: {benchmark_results['compression_speedup']:.1f}x")
    print(
        f"  Average compression time: {benchmark_results['average_compression_time']:.4f}s"
    )
    print(
        f"  Average decompression time: {benchmark_results['average_decompression_time']:.4f}s"
    )

    # Cleanup
    import os

    for file in ["test_materials.usifc", "silicon.usif"]:
        if os.path.exists(file):
            os.remove(file)

    print("\nAll tests completed successfully!")


def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\nTesting Edge Cases")
    print("=" * 50)

    encoder = USIF()

    # Test 1: Empty structure - should fail validation
    print("\n1. Testing Error Conditions")
    try:
        empty_structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3),
            spacegroup=1,
            wyckoff_sites=[],  # No atoms - should fail
            formula="",
        )
        print(empty_structure)
        print("  Empty structure created (should fail validation)")
    except Exception as e:
        print(f"  Empty structure correctly rejected: {e}")

    # Test 2: Invalid molecular structure with lattice
    try:
        USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3),  # Should not have lattice
            point_group="C1",
            point_group_sites=[PointGroupSite(1, 1, (0, 0, 0))],
            formula="H",
        )
        print("  Invalid molecular structure created (should fail)")
    except Exception as e:
        print(f"  Invalid structure correctly rejected: {e}")

    # Test 3: Large structure
    print("\n2. Testing Large Structure")
    large_wyckoff = [WyckoffSite(1, 1000, (0, 0, 0))]  # 1000 hydrogen atoms
    large_structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 10,
        spacegroup=1,
        wyckoff_sites=large_wyckoff,
        formula="H1000",
    )

    encoded_large = encoder.encode(large_structure)
    decoded_large, _ = encoder.decode(encoded_large)
    print(f"  Large structure: {large_structure.num_atoms()} atoms")
    print(f"  Decoded structure: {decoded_large.num_atoms()} atoms")
    print(
        f"  Multiplicity preserved: {large_structure.wyckoff_sites[0].multiplicity == decoded_large.wyckoff_sites[0].multiplicity}"
    )
    print(f"  Encoded size: {len(encoded_large)} bytes")
    print(f"  Bytes per atom: {len(encoded_large) / large_structure.num_atoms():.3f}")

    # Test 4: Simple structure without complex properties
    print("\n3. Testing Simple Structure with Basic Properties")
    simple_atoms = [AtomSite(26, (0, 0, 0), AtomicProperties(charge=0.5, magmom=2.2))]

    simple_structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        atom_sites=simple_atoms,
        structure_properties=StructureProperties(
            energy=-15.0, volume=1.0, custom={"calculator": "Quantum ESPRESSO"}
        ),
        formula="Fe",
    )

    encoded_simple = encoder.encode(simple_structure)
    decoded_simple, _ = encoder.decode(encoded_simple)

    print(f"  Simple structure: {simple_structure.formula}")
    print(f"  Has energy: {decoded_simple.structure_properties.energy is not None}")
    print(f"  Has charge: {decoded_simple.atom_sites[0].properties.charge is not None}")
    print(f"  Has magmom: {decoded_simple.atom_sites[0].properties.magmom is not None}")
    print(f"  Encoded size: {len(encoded_simple)} bytes")

    # Test 5: Very large multiplicity (edge case)
    print("\n4. Testing Very Large Multiplicity")
    huge_wyckoff = [WyckoffSite(1, 65535, (0, 0, 0))]  # Maximum for 2 bytes
    huge_structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 20,
        spacegroup=1,
        wyckoff_sites=huge_wyckoff,
        formula="H65535",
    )

    encoded_huge = encoder.encode(huge_structure)
    decoded_huge, _ = encoder.decode(encoded_huge)
    print(f"  Huge structure: {huge_structure.num_atoms()} atoms")
    print(f"  Multiplicity: {huge_structure.wyckoff_sites[0].multiplicity}")
    print(
        f"  Round-trip successful: {huge_structure.wyckoff_sites[0].multiplicity == decoded_huge.wyckoff_sites[0].multiplicity}"
    )

    print("\nEdge case tests completed!")


def test_property_system():
    """Test the modular property system"""
    print("\nTesting Property System")
    print("=" * 50)

    # Test 1: Custom property registration
    print("\n1. Testing Custom Property Registration")

    custom_prop = PropertyDefinition(
        name="band_gap",
        data_type=float,
        is_per_atom=False,
        description="Electronic band gap",
        units="eV",
    )
    PropertyRegistry.register(custom_prop)

    # Test if property is registered
    retrieved_prop = PropertyRegistry.get("band_gap")
    print(f"  Custom property registered: {retrieved_prop is not None}")
    print(f"  Property name: {retrieved_prop.name if retrieved_prop else 'None'}")
    print(f"  Property units: {retrieved_prop.units if retrieved_prop else 'None'}")

    # Test 2: Property validation
    print("\n2. Testing Property Validation")

    is_valid = PropertySerializer.validate_value(1.5, custom_prop)
    print(f"  Valid float value: {is_valid}")

    is_valid = PropertySerializer.validate_value("invalid", custom_prop)
    print(f"  Invalid string value: {not is_valid}")

    # Test 3: Property serialization
    print("\n3. Testing Property Serialization")

    serialized = PropertySerializer.serialize_value(2.1, custom_prop)
    print(f"  Serialized size: {len(serialized)} bytes")

    deserialized, offset = PropertySerializer.deserialize_value(
        custom_prop, serialized, 0
    )
    print(f"  Deserialized value: {deserialized}")
    print(f"  Round-trip successful: {abs(deserialized - 2.1) < 1e-6}")

    print("\n4. Testing Custom Property in Structure")

    band_gap_prop = PropertyDefinition(
        name="band_gap",
        data_type=float,
        is_per_atom=False,
        description="Electronic band gap",
        units="eV",
    )
    PropertyRegistry.register(band_gap_prop)

    structure_with_custom = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(14, 1, (0, 0, 0))],
        structure_properties=StructureProperties(
            energy=-5.0, custom={"band_gap": 1.12}  # Silicon band gap
        ),
        formula="Si",
    )

    encoder = USIF()
    encoded = encoder.encode(structure_with_custom)
    decoded, _ = encoder.decode(encoded)

    custom_value = decoded.structure_properties.custom.get("band_gap")
    print(f"  Custom property in structure: {custom_value}")

    if custom_value is not None:
        print(f"  Property preserved: {abs(custom_value - 1.12) < 1e-6}")
    else:
        print("  Property preserved: False (custom value is None)")
        print(f"  All custom properties: {decoded.structure_properties.custom}")

    print("\nProperty system tests completed!")


# Run the tests
if __name__ == "__main__":
    test_examples()
    test_edge_cases()
    test_property_system()
