#!/usr/bin/env python3
"""
USIF v2.0 Complete Running Example - Fixed Version
"""

import numpy as np
import tempfile
import os
from pathlib import Path
from monty.serialization import dumpfn, loadfn

# Import the USIF modules
from usif import (
    USIF, USIFStructure, StructureType, StorageMode, CompressionType,
    StructureConverter, EnhancedStructureContainer,
    WyckoffSite, PointGroupSite, AtomSite, AtomicProperties, StructureProperties,
    PropertyRegistry, PropertyDefinition
)


def demo_basic_encoding_decoding():
    """Demo 1: Basic encoding and decoding of crystal structures"""
    print("=" * 60)
    print("DEMO 1: Basic Encoding/Decoding")
    print("=" * 60)
    
    # Create a simple crystal structure (NaCl)
    lattice_matrix = np.array([
        [5.64, 0.0, 0.0],
        [0.0, 5.64, 0.0],
        [0.0, 0.0, 5.64]
    ], dtype=np.float32)
    
    # Using symmetric storage (Wyckoff positions)
    wyckoff_sites = [
        WyckoffSite(atomic_number=11, multiplicity=4, coords=(0.0, 0.0, 0.0)),  # Na
        WyckoffSite(atomic_number=17, multiplicity=4, coords=(0.5, 0.5, 0.5))   # Cl
    ]
    
    structure_props = StructureProperties(
        energy=-10.5,
        volume=179.4,
        calculator="VASP"
    )
    
    structure = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=lattice_matrix,
        spacegroup=225,  # Fm-3m
        wyckoff_sites=wyckoff_sites,
        structure_properties=structure_props,
        formula="NaCl"
    )
    
    # Encode to USIF format
    dumpfn(structure,"NaCl.json")
    encoder = USIF(compression=CompressionType.GZIP)
    encoder.save(structure,"NaCl.usif")
    usif_data = encoder.encode(structure)
    
    print(f"Original structure: {structure.formula}")
    print(f"Number of atoms: {structure.num_atoms()}")
    print(f"USIF data size: {len(usif_data)} bytes")
    print(f"Structure hash: {encoder.get_structure_hash(structure)}")
    
    # Decode back
    decoded_structure, hash_value = encoder.decode(usif_data)
    
    print(f"Decoded structure: {decoded_structure.formula}")
    print(f"Decoded atoms: {decoded_structure.num_atoms()}")
    print(f"Energy: {decoded_structure.structure_properties.energy} eV")
    print(f"Volume: {decoded_structure.structure_properties.volume} Å³")
    
    return structure, encoder


def demo_atomic_properties():
    """Demo 2: Structures with atomic properties"""
    print("\n" + "=" * 60)
    print("DEMO 2: Atomic Properties")
    print("=" * 60)
    
    # Create a water molecule with atomic properties
    atom_sites = [
        AtomSite(
            atomic_number=8,  # Oxygen
            coords=(0.0, 0.0, 0.0),
            properties=AtomicProperties(
                charge=-0.8,
                force=(0.1, -0.05, 0.02)
            )
        ),
        AtomSite(
            atomic_number=1,  # Hydrogen
            coords=(0.76, 0.59, 0.0),
            properties=AtomicProperties(
                charge=0.4,
                force=(-0.05, 0.03, 0.01)
            )
        ),
        AtomSite(
            atomic_number=1,  # Hydrogen
            coords=(-0.76, 0.59, 0.0),
            properties=AtomicProperties(
                charge=0.4,
                force=(-0.05, 0.02, -0.01)
            )
        )
    ]
    
    structure_props = StructureProperties(
        energy=-13.7,
        forces_rms=0.05,
        converged=True
    )
    
    structure = USIFStructure(
        structure_type=StructureType.MOLECULAR,
        storage_mode=StorageMode.FULL_ATOMIC,
        atom_sites=atom_sites,
        structure_properties=structure_props,
        formula="H2O"
    )
    
    encoder = USIF()
    usif_data = encoder.encode(structure)
    
    print(f"Molecule: {structure.formula}")
    print(f"Total energy: {structure.structure_properties.energy} eV")
    print(f"Converged: {structure.structure_properties.converged}")
    
    # Show atomic properties
    for i, atom in enumerate(structure.atom_sites):
        element = "O" if atom.atomic_number == 8 else "H"
        print(f"  Atom {i} ({element}):")
        print(f"    Charge: {atom.properties.charge}")
        print(f"    Force: {atom.properties.force}")
    
    print(f"Encoded size: {len(usif_data)} bytes")
    
    return structure, encoder


def demo_simple_container():
    """Demo 3: Simple container functionality"""
    print("\n" + "=" * 60)
    print("DEMO 3: Simple Container")
    print("=" * 60)
    
    # Create temporary file for demo
    with tempfile.NamedTemporaryFile(suffix='.usifc', delete=False) as tmp:
        container_file = tmp.name
    
    try:
        # Create container in write mode
        with EnhancedStructureContainer(container_file, mode='w', use_mmap=False) as container:
            # Create a simple structure
            lattice_matrix = np.array([
                [4.0, 0.0, 0.0],
                [0.0, 4.0, 0.0],
                [0.0, 0.0, 4.0]
            ])
            
            atom_sites = [
                AtomSite(atomic_number=13, coords=(0.0, 0.0, 0.0)),  # Aluminum
                AtomSite(atomic_number=13, coords=(0.5, 0.5, 0.5)),
            ]
            
            aluminum = USIFStructure(
                structure_type=StructureType.PERIODIC,
                storage_mode=StorageMode.FULL_ATOMIC,
                lattice_matrix=lattice_matrix,
                spacegroup=229,
                atom_sites=atom_sites,
                structure_properties=StructureProperties(energy=-8.7, volume=64.0),
                formula="Al"
            )
            
            # Add structure to container
            hash1 = container.add(aluminum, name="aluminum_crystal")
            print(f"Added aluminum structure with hash: {hash1[:16]}...")
            
            # Create another structure
            diamond_atoms = [
                AtomSite(atomic_number=6, coords=(0.0, 0.0, 0.0)),
                AtomSite(atomic_number=6, coords=(0.25, 0.25, 0.25)),
            ]
            
            diamond = USIFStructure(
                structure_type=StructureType.PERIODIC,
                storage_mode=StorageMode.FULL_ATOMIC,
                lattice_matrix=np.array([[3.57, 0, 0], [0, 3.57, 0], [0, 0, 3.57]]),
                spacegroup=227,
                atom_sites=diamond_atoms,
                structure_properties=StructureProperties(energy=-15.8, volume=45.5),
                formula="C"
            )
            
            hash2 = container.add(diamond, name="diamond")
            print(f"Added diamond structure with hash: {hash2[:16]}...")
            
            # Create groups and organize
            metals_group = container.create_group("/materials/metals")
            carbon_group = container.create_group("/materials/carbon")
            
            print(f"Created groups: {container.list_groups()}")
            
            # Get statistics
            stats = container.stats()
            print(f"Container statistics:")
            print(f"  Total structures: {stats['total_structures']}")
            print(f"  Total groups: {stats['total_groups']}")
            print(f"  Total size: {stats['total_size_bytes']} bytes")
        
        # Reopen container in read mode
        with EnhancedStructureContainer(container_file, mode='r', use_mmap=False) as container:
            print(f"\nReopened container with {len(container)} structures")
            
            # Retrieve structures
            aluminum_retrieved = container.get("aluminum_crystal")
            if aluminum_retrieved:
                print(f"Retrieved: {aluminum_retrieved.formula}")
                print(f"Energy: {aluminum_retrieved.structure_properties.energy} eV")
            
            # Query by formula
            carbon_structures = container.query(formula="C")
            print(f"Found {len(carbon_structures)} carbon structures")
            
            # Query by energy
            low_energy = container.query(energy_range=(-20.0, -10.0))
            print(f"Found {len(low_energy)} structures with energy between -20 and -10 eV")
            
    finally:
        # Clean up
        if os.path.exists(container_file):
            os.unlink(container_file)


def demo_custom_properties():
    """Demo 4: Custom property system"""
    print("\n" + "=" * 60)
    print("DEMO 4: Custom Properties")
    print("=" * 60)
    
    # Register custom properties
    band_gap_def = PropertyDefinition(
        name="band_gap",
        data_type=float,
        is_per_atom=False,
        description="Electronic band gap",
        units="eV"
    )
    
    fermi_energy_def = PropertyDefinition(
        name="fermi_energy", 
        data_type=float,
        is_per_atom=False,
        description="Fermi energy",
        units="eV"
    )
    
    PropertyRegistry.register_custom_property(band_gap_def)
    PropertyRegistry.register_custom_property(fermi_energy_def)
    
    # Create structure with custom properties
    lattice_matrix = np.array([
        [5.43, 0.0, 0.0],
        [0.0, 5.43, 0.0], 
        [0.0, 0.0, 5.43]
    ])
    
    wyckoff_sites = [WyckoffSite(14, 8, (0.0, 0.0, 0.0))]  # Silicon
    
    structure_props = StructureProperties(
        energy=-10.8,
        volume=160.1,
        custom={
            "band_gap": 1.12,
            "fermi_energy": -2.3
        }
    )
    
    silicon = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=lattice_matrix,
        spacegroup=227,
        wyckoff_sites=wyckoff_sites,
        structure_properties=structure_props,
        formula="Si"
    )
    
    # Encode and decode
    encoder = USIF()
    usif_data = encoder.encode(silicon)
    decoded_si, _ = encoder.decode(usif_data)
    
    print(f"Silicon structure: {decoded_si.formula}")
    print(f"Band gap: {decoded_si.structure_properties.custom.get('band_gap')} eV")
    print(f"Fermi energy: {decoded_si.structure_properties.custom.get('fermi_energy')} eV")
    print(f"Custom properties preserved: {len(decoded_si.structure_properties.custom)}")
    
    # List all available properties
    all_props = PropertyRegistry.get_all_properties()
    print(f"\nAvailable properties ({len(all_props)}):")
    for prop_name, prop_def in list(all_props.items())[:8]:  # Show first 8
        print(f"  {prop_name}: {prop_def.description}")


def demo_file_io():
    """Demo 5: File I/O operations"""
    print("\n" + "=" * 60)
    print("DEMO 5: File I/O Operations")
    print("=" * 60)
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.usif', delete=False) as tmp:
        usif_file = tmp.name
    
    try:
        # Create a simple structure
        lattice_matrix = np.array([
            [4.0, 0.0, 0.0],
            [0.0, 4.0, 0.0],
            [0.0, 0.0, 4.0]
        ])
        
        atom_sites = [
            AtomSite(atomic_number=13, coords=(0.0, 0.0, 0.0)),  # Aluminum
            AtomSite(atomic_number=13, coords=(0.5, 0.5, 0.5)),
        ]
        
        aluminum = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=lattice_matrix,
            spacegroup=229,  # Im-3m
            atom_sites=atom_sites,
            structure_properties=StructureProperties(
                energy=-8.7,
                volume=64.0,
                converged=True
            ),
            formula="Al"
        )
        
        # Save to file
        encoder = USIF()
        encoder.save(aluminum, usif_file)
        
        file_size = os.path.getsize(usif_file)
        print(f"Saved structure to: {usif_file}")
        print(f"File size: {file_size} bytes")
        
        # Load from file
        loaded_structure = encoder.load(usif_file)
        
        print(f"Loaded structure: {loaded_structure.formula}")
        print(f"Atoms: {loaded_structure.num_atoms()}")
        print(f"Energy: {loaded_structure.structure_properties.energy} eV")
        print(f"Converged: {loaded_structure.structure_properties.converged}")
        
        # Verify integrity
        original_hash = encoder.get_structure_hash(aluminum)
        loaded_hash = encoder.get_structure_hash(loaded_structure)
        print(f"Hash match: {original_hash == loaded_hash}")
        
    finally:
        # Clean up
        if os.path.exists(usif_file):
            os.unlink(usif_file)


def main():
    """Run all demos"""
    print("USIF v2.0 Complete Running Example - Fixed Version")
    print("Universal Structure Interchange Format")
    print("=" * 60)
    
    # Run all demos
    demo_basic_encoding_decoding()
    demo_atomic_properties()
    demo_simple_container()  # Replaced enhanced container with simple version
    demo_custom_properties()
    demo_file_io()
    
    print("\n" + "=" * 60)
    print("All demos completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
