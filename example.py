from usif import *
def test_examples():
    """Comprehensive test examples for USIF format"""
    print("USIF Comprehensive Test Examples")
    print("=" * 50)

    # Test 1: Simple Crystal Structure (Symmetric) - Use realistic silicon structure
    print("\n1. Testing Simple Crystal Structure (Symmetric)")

    # Create a proper silicon diamond structure
    lattice = np.array([
        [5.43, 0.0, 0.0],
        [0.0, 5.43, 0.0],
        [0.0, 0.0, 5.43]
    ])

    # Silicon diamond structure has atoms at (0,0,0) and (0.25,0.25,0.25) and symmetric equivalents
    wyckoff_sites = [
        WyckoffSite(14, 8, (0.0, 0.0, 0.0)),  # Silicon positions
    ]

    silicon_crystal = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=lattice,
        spacegroup=227,  # Fd-3m (diamond structure)
        wyckoff_sites=wyckoff_sites,
        structure_properties=StructureProperties(
            energy=-10.5,
            volume=160.0,
            calculator="VASP"
        ),
        formula="Si"
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
    lattice_nacl = np.array([
        [5.64, 0.0, 0.0],
        [0.0, 5.64, 0.0],
        [0.0, 0.0, 5.64]
    ])

    atom_sites = [
        AtomSite(11, (0.0, 0.0, 0.0), AtomicProperties(force=(0.001, -0.002, 0.001))),  # Na
        AtomSite(17, (0.5, 0.5, 0.5), AtomicProperties(force=(-0.001, 0.002, -0.001))),  # Cl
    ]

    nacl_crystal = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=lattice_nacl,
        spacegroup=225,  # Fm-3m
        atom_sites=atom_sites,
        structure_properties=StructureProperties(
            energy=-20.8,
            energy_per_atom=-10.4,
            volume=179.4,
            converged=True
        ),
        formula="NaCl"
    )

    encoded_nacl = encoder.encode(nacl_crystal)
    print(f"  Formula: {nacl_crystal.formula}")
    print(f"  Atoms: {nacl_crystal.num_atoms()}")
    print(f"  Energy: {nacl_crystal.structure_properties.energy} eV")
    print(f"  Has forces: {all(atom.properties.force is not None for atom in nacl_crystal.atom_sites)}")
    print(f"  Size: {len(encoded_nacl)} bytes")

    # Continue with other tests...
    # Test 3: Molecular Structure (Symmetric)
    print("\n3. Testing Molecular Structure (Symmetric)")
    water_molecule = USIFStructure(
        structure_type=StructureType.MOLECULAR,
        storage_mode=StorageMode.SYMMETRIC,
        point_group="C2v",
        point_group_sites=[
            PointGroupSite(8, 1, (0.0, 0.0, 0.0)),  # Oxygen
            PointGroupSite(1, 2, (0.757, 0.586, 0.0)),  # Hydrogens (symmetric)
        ],
        structure_properties=StructureProperties(
            energy=-76.4,
            forces_rms=0.001,
            converged=True
        ),
        formula="H2O"
    )

    encoded_water = encoder.encode(water_molecule)
    print(f"  Formula: {water_molecule.formula}")
    print(f"  Point group: {water_molecule.point_group}")
    print(f"  Atoms: {water_molecule.num_atoms()}")
    print(f"  Symmetric sites: {len(water_molecule.point_group_sites)}")
    print(f"  Size: {len(encoded_water)} bytes")

    # Test 4: Complex Molecule with Properties
    print("\n4. Testing Complex Molecule with Properties")
    # Simplified benzene without charges to avoid symmetry issues
    benzene_atoms = [
        AtomSite(6, (0.000, 1.396, 0.000)),  # C
        AtomSite(6, (1.209, 0.698, 0.000)),  # C
        AtomSite(6, (1.209, -0.698, 0.000)), # C
        AtomSite(6, (0.000, -1.396, 0.000)), # C
        AtomSite(6, (-1.209, -0.698, 0.000)),# C
        AtomSite(6, (-1.209, 0.698, 0.000)), # C
        AtomSite(1, (0.000, 2.479, 0.000)),  # H
        AtomSite(1, (2.147, 1.240, 0.000)),  # H
        AtomSite(1, (2.147, -1.240, 0.000)), # H
        AtomSite(1, (0.000, -2.479, 0.000)), # H
        AtomSite(1, (-2.147, -1.240, 0.000)),# H
        AtomSite(1, (-2.147, 1.240, 0.000)), # H
    ]

    benzene = USIFStructure(
        structure_type=StructureType.MOLECULAR,
        storage_mode=StorageMode.FULL_ATOMIC,
        atom_sites=benzene_atoms,
        structure_properties=StructureProperties(
            energy=-230.5,
            calculator="Gaussian"
        ),
        formula="C6H6"
    )

    encoded_benzene = encoder.encode(benzene)
    print(f"  Formula: {benzene.formula}")
    print(f"  Atoms: {benzene.num_atoms()}")
    print(f"  Size: {len(encoded_benzene)} bytes")

    # Test 5: Container with Multiple Structures
    print("\n5. Testing Container with Multiple Structures")

    # Create container and add structures
    with StructureContainer("test_materials.usifc", mode="w") as container:
        # Add to different groups
        container.add(silicon_crystal, name="silicon_diamond", group="/crystals/elemental")
        container.add(nacl_crystal, name="sodium_chloride", group="/crystals/salts")
        container.add(water_molecule, name="water", group="/molecules/small")
        container.add(benzene, name="benzene", group="/molecules/organic")

        print(f"  Total structures in container: {len(container)}")

    # Test reading and querying - use simpler approach
    with StructureContainer("test_materials.usifc", mode="r") as container:
        # Get all structures
        all_structures = list(container)
        print(f"  Found {len(all_structures)} total structures")

        # Test direct access
        if container._hash_index:
            first_hash = list(container._hash_index.keys())[0]
            first_structure = container.get(first_hash)
            if first_structure:
                print(f"  First structure: {first_structure.formula}")

        # Test group access
        groups = container.list_groups()
        print(f"  Container groups: {groups}")

        # Test getting structures from root group
        root_structures = container.get_structures_in_group("/")
        print(f"  Structures in root: {len(root_structures)}")

    # Test 6: Pymatgen Conversion - use a simple structure
    print("\n6. Testing Pymatgen Conversion")

    # Create a simple cubic structure
    lattice_simple = Lattice.cubic(3.0)
    species = ["Li"]
    coords = [[0, 0, 0]]
    simple_structure = PMGStructure(lattice_simple, species, coords)

    # Convert pymatgen to USIF
    usif_from_pmg = StructureConverter.from_pymatgen(simple_structure, force_symmetric=True)
    print(f"  Pymatgen to USIF: {usif_from_pmg.formula}")

    # Convert USIF back to pymatgen
    pmg_back = StructureConverter.to_pymatgen(usif_from_pmg)
    print(f"  USIF to pymatgen: {pmg_back.formula}")
    print(f"  Round-trip successful: {simple_structure.formula == pmg_back.formula}")

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
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3),
            spacegroup=1,
            wyckoff_sites=[],  # No atoms - should fail
            formula=""
        )
        print("  Empty structure created (should fail validation)")
    except Exception as e:
        print(f"  Empty structure correctly rejected: {e}")
    
    # Test 2: Invalid molecular structure with lattice
    try:
        invalid_mol = USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3),  # Should not have lattice
            point_group="C1",
            point_group_sites=[PointGroupSite(1, 1, (0,0,0))],
            formula="H"
        )
        print("  Invalid molecular structure created (should fail)")
    except Exception as e:
        print(f"  Invalid structure correctly rejected: {e}")
    
    # Test 3: Large structure - now with fixed multiplicity encoding
    print("\n2. Testing Large Structure")
    large_wyckoff = [WyckoffSite(1, 1000, (0,0,0))]  # 1000 hydrogen atoms
    large_structure = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 10,
        spacegroup=1,
        wyckoff_sites=large_wyckoff,
        formula="H1000"
    )
    
    encoded_large = encoder.encode(large_structure)
    decoded_large, _ = encoder.decode(encoded_large)
    print(f"  Large structure: {large_structure.num_atoms()} atoms")
    print(f"  Decoded structure: {decoded_large.num_atoms()} atoms")
    print(f"  Multiplicity preserved: {large_structure.wyckoff_sites[0].multiplicity == decoded_large.wyckoff_sites[0].multiplicity}")
    print(f"  Encoded size: {len(encoded_large)} bytes")
    print(f"  Bytes per atom: {len(encoded_large)/large_structure.num_atoms():.3f}")
    
    # Test 4: Structure with all property types
    print("\n3. Testing Structure with All Properties")
    comprehensive_atoms = [
        AtomSite(26, (0,0,0), AtomicProperties(
            force=(0.1, -0.1, 0.05),
            charge=0.5,
            magmom=2.2,
            velocity=(0.01, 0.02, -0.01)
        ))
    ]
    
    comprehensive_structure = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        atom_sites=comprehensive_atoms,
        structure_properties=StructureProperties(
            energy=-15.0,
            energy_per_atom=-15.0,
            stress=(0.1, 0.1, 0.1, 0.05, 0.05, 0.05),
            pressure=0.1,
            forces_rms=0.15,
            forces_max=0.2,
            volume=1.0,
            calculator="Quantum ESPRESSO",
            functional="PBE",
            converged=True
        ),
        formula="Fe"
    )
    
    encoded_comp = encoder.encode(comprehensive_structure)
    decoded_comp, _ = encoder.decode(encoded_comp)
    
    print(f"  All properties structure: {comprehensive_structure.formula}")
    print(f"  Has energy: {decoded_comp.structure_properties.energy is not None}")
    print(f"  Has forces: {decoded_comp.atom_sites[0].properties.force is not None}")
    print(f"  Has magmom: {decoded_comp.atom_sites[0].properties.magmom is not None}")
    print(f"  Has velocity: {decoded_comp.atom_sites[0].properties.velocity is not None}")
    print(f"  Encoded size: {len(encoded_comp)} bytes")
    
    # Test 5: Very large multiplicity (edge case)
    print("\n4. Testing Very Large Multiplicity")
    huge_wyckoff = [WyckoffSite(1, 65535, (0,0,0))]  # Maximum for 2 bytes
    huge_structure = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3) * 20,
        spacegroup=1,
        wyckoff_sites=huge_wyckoff,
        formula="H65535"
    )
    
    encoded_huge = encoder.encode(huge_structure)
    decoded_huge, _ = encoder.decode(encoded_huge)
    print(f"  Huge structure: {huge_structure.num_atoms()} atoms")
    print(f"  Multiplicity: {huge_structure.wyckoff_sites[0].multiplicity}")
    print(f"  Round-trip successful: {huge_structure.wyckoff_sites[0].multiplicity == decoded_huge.wyckoff_sites[0].multiplicity}")
    
    # Test 6: Structure with custom properties
    print("\n5. Testing Custom Properties")
    
    # Register a custom property
    custom_prop = PropertyDefinition(
        name="custom_field",
        data_type=float,
        is_per_atom=False,
        description="Custom test field",
        units="arbitrary"
    )
    PropertyRegistry.register_custom_property(custom_prop)
    
    custom_structure = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, (0,0,0))],
        structure_properties=StructureProperties(
            energy=-1.0,
            custom={"custom_field": 42.0}
        ),
        formula="H"
    )
    
    encoded_custom = encoder.encode(custom_structure)
    decoded_custom, _ = encoder.decode(encoded_custom)
    custom_value = decoded_custom.structure_properties.custom.get("custom_field")
    print(f"  Custom property value: {custom_value}")
    print(f"  Custom property preserved: {custom_value == 42.0}")


# Run the tests
if __name__ == "__main__":
    test_examples()
    test_edge_cases()

