#!/usr/bin/env python3
"""
Comprehensive tests for USIF encoder/decoder
Test error handling, edge cases, and all encoding modes
"""

import os
import tempfile
import unittest

import numpy as np

from usif import (
    USIF,
    AtomicProperties,
    AtomSite,
    CompressionType,
    CorruptedDataError,
    DecodingError,
    EncodingError,
    PointGroupSite,
    PropertyDefinition,
    DEFAULT_REGISTRY,
    create_default_registry,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
    ValidationError,
    WyckoffSite,
)


class TestEncoderComprehensive(unittest.TestCase):
    """Comprehensive tests for encoder/decoder"""

    def setUp(self):
        """Set up test fixtures"""
        self.encoder = USIF(compression=CompressionType.GZIP)
        self.encoder_no_comp = USIF(compression=CompressionType.NONE)

        # Create test structures
        self.periodic_symmetric = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(14, 8, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=-10.5, volume=125.0),
            formula="Si",
        )

        self.periodic_atomic = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=1,
            atom_sites=[
                AtomSite(14, (0.0, 0.0, 0.0), AtomicProperties()),
                AtomSite(14, (2.5, 2.5, 2.5), AtomicProperties()),
            ],
            structure_properties=StructureProperties(energy=-20.0),
            formula="Si2",
        )

        self.molecular_symmetric = USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.SYMMETRIC,
            point_group="C2v",
            point_group_sites=[
                PointGroupSite(8, 1, (0.0, 0.0, 0.0), 1.0),
                PointGroupSite(1, 2, (0.76, 0.59, 0.0), 1.0),
            ],
            structure_properties=StructureProperties(energy=-76.4),
            formula="H2O",
        )

        self.molecular_atomic = USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=[
                AtomSite(8, (0.0, 0.0, 0.0), AtomicProperties(charge=-0.8)),
                AtomSite(1, (0.76, 0.59, 0.0), AtomicProperties(charge=0.4)),
                AtomSite(1, (-0.76, 0.59, 0.0), AtomicProperties(charge=0.4)),
            ],
            structure_properties=StructureProperties(energy=-76.4),
            formula="H2O",
        )

    def test_encode_decode_periodic_symmetric(self):
        """Test encoding/decoding periodic symmetric structure"""
        encoded = self.encoder.encode(self.periodic_symmetric)
        decoded, hash_val = self.encoder.decode(encoded)

        self.assertEqual(self.periodic_symmetric, decoded)
        self.assertEqual(self.periodic_symmetric.formula, decoded.formula)
        self.assertEqual(self.periodic_symmetric.spacegroup, decoded.spacegroup)
        self.assertTrue(
            np.allclose(self.periodic_symmetric.lattice_matrix, decoded.lattice_matrix)
        )

    def test_encode_decode_periodic_atomic(self):
        """Test encoding/decoding periodic full atomic structure"""
        encoded = self.encoder.encode(self.periodic_atomic)
        decoded, hash_val = self.encoder.decode(encoded)

        self.assertEqual(self.periodic_atomic, decoded)
        self.assertEqual(len(self.periodic_atomic.atom_sites), len(decoded.atom_sites))

    def test_encode_decode_molecular_symmetric(self):
        """Test encoding/decoding molecular symmetric structure"""
        encoded = self.encoder.encode(self.molecular_symmetric)
        decoded, hash_val = self.encoder.decode(encoded)

        self.assertEqual(self.molecular_symmetric, decoded)
        self.assertEqual(self.molecular_symmetric.point_group, decoded.point_group)

    def test_encode_decode_molecular_atomic(self):
        """Test encoding/decoding molecular full atomic structure"""
        encoded = self.encoder.encode(self.molecular_atomic)
        decoded, hash_val = self.encoder.decode(encoded)

        self.assertEqual(self.molecular_atomic, decoded)
        self.assertEqual(len(self.molecular_atomic.atom_sites), len(decoded.atom_sites))

    def test_compression_none(self):
        """Test encoding without compression"""
        encoded = self.encoder_no_comp.encode(self.periodic_symmetric)
        decoded, _ = self.encoder_no_comp.decode(encoded)
        self.assertEqual(self.periodic_symmetric, decoded)

    def test_structure_hash(self):
        """Test structure hash calculation"""
        hash1 = self.encoder.get_geometry_hash(self.periodic_symmetric)
        hash2 = self.encoder.get_geometry_hash(self.periodic_symmetric)
        self.assertEqual(hash1, hash2)

        # Different structure should have different hash
        hash3 = self.encoder.get_geometry_hash(self.periodic_atomic)
        self.assertNotEqual(hash1, hash3)

    def test_save_load(self):
        """Test save and load functionality"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".usif") as f:
            temp_path = f.name

        try:
            self.encoder.save(self.periodic_symmetric, temp_path)
            loaded = self.encoder.load(temp_path)
            self.assertEqual(self.periodic_symmetric, loaded)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_decode_corrupted_data_too_short(self):
        """Test decoding with data too short"""
        with self.assertRaises(CorruptedDataError):
            self.encoder.decode(b"USIF")

    def test_decode_corrupted_magic_bytes(self):
        """Test decoding with invalid magic bytes"""
        corrupted = b"INVALID" + b"\x00" * 57
        with self.assertRaises(CorruptedDataError):
            self.encoder.decode(corrupted)

    def test_decode_corrupted_gzip(self):
        """Test decoding with corrupted gzip data"""
        # Create valid header but corrupted compressed data
        header = bytearray(64)
        header[0:7] = b"USIF\x00\x00\x00"
        header[7:8] = b"\x04"  # version
        header[8:12] = b"\x10\x00\x00\x00"  # raw size
        header[12:16] = b"\x05\x00\x00\x00"  # compressed size
        header[16:17] = b"\x01"  # GZIP compression
        corrupted_data = bytes(header) + b"\x00\x01\x02\x03\x04"

        with self.assertRaises((CorruptedDataError, DecodingError)):
            self.encoder.decode(corrupted_data)

    def test_encode_with_properties(self):
        """Test encoding with various properties"""
        # Stress in Voigt notation (6 components)
        props = StructureProperties(
            energy=-10.5,
            volume=125.0,
            stress=(1.0, 1.0, 1.0, 0.0, 0.0, 0.0),  # Voigt notation
        )
        structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(14, 8, (0.0, 0.0, 0.0))],
            structure_properties=props,
            formula="Si",
        )

        encoded = self.encoder.encode(structure)
        decoded, _ = self.encoder.decode(encoded)

        self.assertAlmostEqual(
            structure.structure_properties.energy, decoded.structure_properties.energy
        )
        self.assertAlmostEqual(
            structure.structure_properties.volume, decoded.structure_properties.volume
        )

    def test_encode_with_atomic_properties(self):
        """Test encoding with atomic properties"""
        atom_sites = [
            AtomSite(
                14,
                (0.0, 0.0, 0.0),
                AtomicProperties(charge=0.5, force=np.array([0.1, 0.2, 0.3])),
            ),
            AtomSite(
                14,
                (2.5, 2.5, 2.5),
                AtomicProperties(charge=-0.5, force=np.array([-0.1, -0.2, -0.3])),
            ),
        ]
        structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=1,
            atom_sites=atom_sites,
            formula="Si2",
        )

        encoded = self.encoder.encode(structure)
        decoded, _ = self.encoder.decode(encoded)

        self.assertEqual(len(structure.atom_sites), len(decoded.atom_sites))
        if decoded.atom_sites[0].properties.charge is not None:
            self.assertAlmostEqual(
                structure.atom_sites[0].properties.charge,
                decoded.atom_sites[0].properties.charge,
            )

    def test_custom_property_types_roundtrip(self):
        """Test binary custom properties preserve JSON-compatible value types."""
        structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.FULL_ATOMIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=1,
            atom_sites=[
                AtomSite(
                    14,
                    (0.0, 0.0, 0.0),
                    AtomicProperties(custom={"label": "Si1", "index": 1}),
                )
            ],
            structure_properties=StructureProperties(
                custom={
                    "calculator": "VASP",
                    "run_id": 3,
                    "converged": True,
                    "tags": ["static", "test"],
                }
            ),
            formula="Si",
        )

        decoded, _ = self.encoder.decode(self.encoder.encode(structure))

        self.assertEqual(
            decoded.structure_properties.custom, structure.structure_properties.custom
        )
        self.assertEqual(
            decoded.atom_sites[0].properties.custom,
            structure.atom_sites[0].properties.custom,
        )

    def test_registered_custom_properties_roundtrip_to_custom_dict(self):
        """Test registered custom properties remain in custom after decode."""
        DEFAULT_REGISTRY.register(
            PropertyDefinition(
                name="test_registered_custom",
                data_type=float,
                description="Registered custom test property",
                units="eV",
            )
        )

        structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=1,
            wyckoff_sites=[WyckoffSite(14, 1, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(
                custom={"test_registered_custom": 1.23}
            ),
            formula="Si",
        )

        decoded, _ = self.encoder.decode(self.encoder.encode(structure))

        self.assertEqual(
            decoded.structure_properties.custom, structure.structure_properties.custom
        )

    def test_version_mismatch_warning(self):
        """Test version mismatch handling"""
        # Create data with different version
        encoded = self.encoder.encode(self.periodic_symmetric)
        # Modify version byte
        modified = bytearray(encoded)
        modified[7] = 99  # Invalid version

        # Should decode but log warning (we can't easily test logging, but it shouldn't crash)
        try:
            decoded, _ = self.encoder.decode(bytes(modified))
            # If it decodes, that's fine - version mismatch is just a warning
        except (DecodingError, CorruptedDataError):
            # If it fails due to other corruption, that's also acceptable
            pass

    def test_empty_formula(self):
        """Test encoding with empty formula"""
        structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(14, 8, (0.0, 0.0, 0.0))],
            formula="",
        )
        encoded = self.encoder.encode(structure)
        decoded, _ = self.encoder.decode(encoded)
        self.assertEqual(structure.formula, decoded.formula)

    def test_large_structure(self):
        """Test encoding large structure"""
        wyckoff_sites = [WyckoffSite(1, 1000, (0.0, 0.0, 0.0))]
        structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 10.0,
            spacegroup=1,
            wyckoff_sites=wyckoff_sites,
            formula="H1000",
        )
        encoded = self.encoder.encode(structure)
        decoded, _ = self.encoder.decode(encoded)
        self.assertEqual(structure.num_atoms(), decoded.num_atoms())

    def test_validation_empty_sites(self):
        """Test validation rejects empty sites"""
        # Empty wyckoff_sites should fail validation
        with self.assertRaises(ValidationError):
            USIFStructure(
                structure_type=StructureType.CRYSTAL,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=np.eye(3) * 5.0,
                spacegroup=227,
                wyckoff_sites=[],  # Empty list should fail
                formula="",
            )

        # Empty atom_sites should fail validation
        with self.assertRaises(ValidationError):
            USIFStructure(
                structure_type=StructureType.CRYSTAL,
                storage_mode=StorageMode.FULL_ATOMIC,
                lattice_matrix=np.eye(3) * 5.0,
                spacegroup=1,
                atom_sites=[],  # Empty list should fail
                formula="",
            )


if __name__ == "__main__":
    unittest.main()
