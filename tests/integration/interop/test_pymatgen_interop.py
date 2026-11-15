#!/usr/bin/env python3
"""
Tests for USIF pymatgen interop adapters
Test conversion between USIF and pymatgen formats
"""

import unittest

import numpy as np
import pytest

pytest.importorskip("pymatgen")
from pymatgen.core import Lattice, Molecule, Structure  # noqa: E402

from usif import StorageMode, StructureType, USIFStructure
from usif.exceptions import SymmetryAnalysisError
from usif.interop.pymatgen import PymatgenExporter, PymatgenImporter
from usif.services import export_structure, load_structure


class TestPymatgenInterop(unittest.TestCase):
    """Test pymatgen import/export adapters"""

    def test_from_pymatgen_structure(self):
        """Test converting from pymatgen Structure"""
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])

        usif_structure = PymatgenImporter.from_pymatgen(structure)
        self.assertIsInstance(usif_structure, USIFStructure)
        self.assertTrue(usif_structure.is_crystal())
        self.assertEqual(usif_structure.num_atoms(), 2)

    def test_from_pymatgen_molecule(self):
        """Test converting from pymatgen Molecule"""
        coords = [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]]
        molecule = Molecule(["O", "H", "H"], coords)

        usif_structure = PymatgenImporter.from_pymatgen(molecule)
        self.assertIsInstance(usif_structure, USIFStructure)
        self.assertTrue(usif_structure.is_molecular())
        self.assertEqual(usif_structure.num_atoms(), 3)

    def test_from_pymatgen_with_properties(self):
        """Test converting with properties"""
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])

        forces = np.array([[0.1, 0.2, 0.3]])
        energy = -10.5

        usif_structure = PymatgenImporter.from_pymatgen(
            structure, forces=forces, energy=energy, calculator="VASP"
        )
        self.assertAlmostEqual(
            usif_structure.structure_properties.energy, energy, places=5
        )
        self.assertIn("calculator", usif_structure.structure_properties.custom)

    def test_to_pymatgen_structure(self):
        """Test converting to pymatgen Structure"""
        import numpy as np

        from usif import StructureProperties, WyckoffSite

        lattice_matrix = np.eye(3) * 5.0
        wyckoff_sites = [WyckoffSite(14, 2, (0.0, 0.0, 0.0))]

        usif_structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice_matrix,
            spacegroup=227,
            wyckoff_sites=wyckoff_sites,
            formula="Si",
        )

        pmg_structure = PymatgenExporter.to_pymatgen(usif_structure)
        self.assertIsInstance(pmg_structure, Structure)
        self.assertEqual(len(pmg_structure), 2)

    def test_to_pymatgen_molecule(self):
        """Test converting to pymatgen Molecule"""
        from usif import AtomicProperties, AtomSite

        atom_sites = [
            AtomSite(8, (0.0, 0.0, 0.0)),
            AtomSite(1, (0.76, 0.59, 0.0)),
            AtomSite(1, (-0.76, 0.59, 0.0)),
        ]

        usif_structure = USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=atom_sites,
            formula="H2O",
        )

        pmg_molecule = PymatgenExporter.to_pymatgen(usif_structure)
        self.assertIsInstance(pmg_molecule, Molecule)
        self.assertEqual(len(pmg_molecule), 3)

    def test_roundtrip_structure(self):
        """Test roundtrip conversion for structure"""
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])

        usif_structure = PymatgenImporter.from_pymatgen(structure)
        pmg_structure = PymatgenExporter.to_pymatgen(usif_structure)

        self.assertEqual(len(structure), len(pmg_structure))
        self.assertAlmostEqual(structure.volume, pmg_structure.volume, places=3)

        original_coords = {tuple(round(float(x), 6) for x in site.frac_coords) for site in structure}
        roundtrip_coords = {
            tuple(round(float(x), 6) for x in site.frac_coords)
            for site in pmg_structure
        }
        self.assertEqual(roundtrip_coords, original_coords)

    def test_roundtrip_molecule(self):
        """Test roundtrip conversion for molecule"""
        coords = [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]]
        molecule = Molecule(["O", "H", "H"], coords)

        usif_structure = PymatgenImporter.from_pymatgen(molecule)
        pmg_molecule = PymatgenExporter.to_pymatgen(usif_structure)

        self.assertEqual(len(molecule), len(pmg_molecule))

        original_coords = {tuple(round(float(x), 6) for x in site.coords) for site in molecule}
        roundtrip_coords = {
            tuple(round(float(x), 6) for x in site.coords)
            for site in pmg_molecule
        }
        self.assertEqual(roundtrip_coords, original_coords)


class TestStructureExportService(unittest.TestCase):
    """Test canonical structure export service"""

    def setUp(self):
        """Set up test fixtures"""
        import numpy as np

        from usif import StructureProperties, WyckoffSite

        # Create a simple crystal structure
        self.lattice_matrix = np.eye(3) * 5.0
        self.wyckoff_sites = [WyckoffSite(14, 2, (0.0, 0.0, 0.0))]

        self.usif_structure = USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=self.lattice_matrix,
            spacegroup=227,
            wyckoff_sites=self.wyckoff_sites,
            formula="Si",
        )

    def test_to_usif_format(self):
        """Test converting to USIF format"""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".usif", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Test with auto-detection from extension
            export_structure(self.usif_structure, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            # Test with explicit format
            with tempfile.NamedTemporaryFile(suffix=".usif", delete=False) as tmp2:
                tmp_path2 = tmp2.name
            export_structure(self.usif_structure, tmp_path2, "usif")
            self.assertTrue(os.path.exists(tmp_path2))
            os.unlink(tmp_path2)

            # Test loading back
            loaded = load_structure(tmp_path)
            self.assertEqual(loaded.formula, self.usif_structure.formula)
            self.assertEqual(loaded.num_atoms(), self.usif_structure.num_atoms())
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_to_usif_format_missing_filename(self):
        """Test that to() raises error when filename is missing for usif format"""
        with self.assertRaises(ValueError) as context:
            export_structure(self.usif_structure, None, "usif")
        self.assertIn("filename is required", str(context.exception))

    def test_to_pymatgen_format(self):
        """Test converting to pymatgen format"""
        pmg_structure = export_structure(self.usif_structure, fmt="pymatgen")

        from pymatgen.core import Structure

        self.assertIsInstance(pmg_structure, Structure)
        self.assertEqual(len(pmg_structure), 2)  # 2 Si atoms
        self.assertAlmostEqual(pmg_structure.volume, 125.0, places=1)

        # Object export needs an explicit format: pymatgen is optional, so
        # the returned type never depends on what happens to be installed.
        with self.assertRaises(ValueError):
            export_structure(self.usif_structure)

        # Test that providing filename with pymatgen raises error
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with self.assertRaises(ValueError) as context:
                export_structure(self.usif_structure, tmp_path, "pymatgen")
            self.assertIn("filename should not be provided", str(context.exception))
        finally:
            import os

            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_to_ase_format(self):
        """Test converting to ASE format"""
        try:
            ase_atoms = export_structure(self.usif_structure, fmt="ase")

            from ase import Atoms

            self.assertIsInstance(ase_atoms, Atoms)
            self.assertEqual(len(ase_atoms), 2)  # 2 Si atoms

            # Check that it has a cell (periodic structure)
            self.assertIsNotNone(ase_atoms.cell)

            # Test that providing filename with ase raises error
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                with self.assertRaises(ValueError) as context:
                    export_structure(self.usif_structure, tmp_path, "ase")
                self.assertIn("filename should not be provided", str(context.exception))
            finally:
                import os

                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except ImportError:
            self.skipTest("ASE is not installed")

    def test_to_cif_format(self):
        """Test converting to CIF format"""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".cif", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Test auto-detection from extension
            export_structure(self.usif_structure, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            # Test explicit format
            with tempfile.NamedTemporaryFile(suffix=".cif", delete=False) as tmp2:
                tmp_path2 = tmp2.name
            export_structure(self.usif_structure, tmp_path2, "cif")
            self.assertTrue(os.path.exists(tmp_path2))
            os.unlink(tmp_path2)

            # Verify it's a valid CIF file
            with open(tmp_path, "r") as f:
                content = f.read()
                self.assertIn("data_", content.lower())
                self.assertIn("Si", content)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_to_poscar_format(self):
        """Test converting to POSCAR format"""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".poscar", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Test auto-detection from extension
            export_structure(self.usif_structure, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            # Verify it's a valid POSCAR file
            with open(tmp_path, "r") as f:
                content = f.read()
                self.assertIn("Si", content)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_to_xyz_format(self):
        """Test converting to XYZ format"""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Test auto-detection from extension
            export_structure(self.usif_structure, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            # Verify it's a valid XYZ file
            with open(tmp_path, "r") as f:
                lines = f.readlines()
                self.assertGreaterEqual(len(lines), 2)
                # First line should be number of atoms
                self.assertEqual(int(lines[0].strip()), 2)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_to_file_format_missing_filename(self):
        """Test that to() raises error when filename is missing for file formats"""
        with self.assertRaises(ValueError) as context:
            export_structure(self.usif_structure, None, "cif")
        self.assertIn("filename is required", str(context.exception))

    def test_to_unsupported_format(self):
        """Test that to() raises error for unsupported formats"""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with self.assertRaises(ValueError) as context:
                export_structure(self.usif_structure, tmp_path, "unsupported_format")
            self.assertIn("not supported", str(context.exception).lower())
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_to_with_properties(self):
        """Test that properties are preserved when converting"""
        import numpy as np

        from usif import StructureProperties

        # Add properties to structure
        self.usif_structure.structure_properties.energy = -10.5
        self.usif_structure.structure_properties.volume = 125.0

        # Convert to pymatgen and back
        pmg_structure = export_structure(self.usif_structure, fmt="pymatgen")
        usif_back = PymatgenImporter.from_pymatgen(pmg_structure)

        # Energy might not be preserved in pymatgen, but structure should be
        self.assertEqual(usif_back.num_atoms(), self.usif_structure.num_atoms())

    def test_to_molecule_format(self):
        """Test converting molecule to various formats"""
        from usif import AtomSite

        # Create a molecule
        atom_sites = [
            AtomSite(8, (0.0, 0.0, 0.0)),
            AtomSite(1, (0.76, 0.59, 0.0)),
            AtomSite(1, (-0.76, 0.59, 0.0)),
        ]

        usif_molecule = USIFStructure(
            structure_type=StructureType.MOLECULE,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=atom_sites,
            formula="H2O",
        )

        # Test to pymatgen
        pmg_molecule = export_structure(usif_molecule, fmt="pymatgen")
        from pymatgen.core import Molecule

        self.assertIsInstance(pmg_molecule, Molecule)
        self.assertEqual(len(pmg_molecule), 3)

        # Test to ASE
        try:
            ase_atoms = export_structure(usif_molecule, fmt="ase")
            from ase import Atoms

            self.assertIsInstance(ase_atoms, Atoms)
            self.assertEqual(len(ase_atoms), 3)
        except ImportError:
            self.skipTest("ASE is not installed")

        # Test to XYZ (auto-detect from extension)
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            export_structure(usif_molecule, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
