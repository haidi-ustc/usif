#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures for USIF tests

This module provides:
- Path setup for imports
- Common fixtures for test data
- Utilities for creating test structures
- Handling of optional dependencies
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Try to import optional dependencies, set flags if missing
HAS_NUMPY = False
HAS_PYMATGEN = False
HAS_MONTY = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    np = None

try:
    import pymatgen
    from pymatgen.core import Lattice, Molecule, Structure

    HAS_PYMATGEN = True
except ImportError:
    pymatgen = None
    Lattice = None
    Molecule = None
    Structure = None

try:
    from monty.json import MSONable

    HAS_MONTY = True
except ImportError:
    MSONable = None

# Import core modules that don't require dependencies
import importlib.util

# Direct import of constants to avoid __init__.py issues
constants_spec = importlib.util.spec_from_file_location(
    "constants", PROJECT_ROOT / "usif" / "constants.py"
)
constants = importlib.util.module_from_spec(constants_spec)
constants_spec.loader.exec_module(constants)

# Direct import of exceptions
exceptions_spec = importlib.util.spec_from_file_location(
    "exceptions", PROJECT_ROOT / "usif" / "exceptions.py"
)
exceptions = importlib.util.module_from_spec(exceptions_spec)
exceptions_spec.loader.exec_module(exceptions)

# Make constants and exceptions available
BinaryFormat = constants.BinaryFormat
CompressionType = constants.CompressionType
StorageMode = constants.StorageMode
StructureType = constants.StructureType
SymmetryConstants = constants.SymmetryConstants

USIFError = exceptions.USIFError
EncodingError = exceptions.EncodingError
DecodingError = exceptions.DecodingError
ValidationError = exceptions.ValidationError
CorruptedDataError = exceptions.CorruptedDataError
SymmetryAnalysisError = exceptions.SymmetryAnalysisError
StorageError = exceptions.StorageError

# Pytest fixtures
import pytest


@pytest.fixture
def temp_file():
    """Create a temporary file and clean up after test"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".usif") as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    if Path(temp_path).exists():
        Path(temp_path).unlink()


@pytest.fixture
def temp_dir():
    """Create a temporary directory and clean up after test"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    import shutil

    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def temp_container_file():
    """Create a temporary container file and clean up after test"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".usifc") as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    if Path(temp_path).exists():
        Path(temp_path).unlink()


@pytest.fixture
def simple_lattice():
    """Create a simple cubic lattice matrix"""
    if not HAS_NUMPY:
        pytest.skip("numpy not available")
    return np.eye(3) * 5.0


@pytest.fixture
def simple_wyckoff_site():
    """Create a simple Wyckoff site for testing"""
    if not HAS_NUMPY:
        pytest.skip("numpy not available")
    # Import here to avoid issues if dependencies missing
    from usif.structures.sites import WyckoffSite

    return WyckoffSite(atomic_number=14, multiplicity=8, coords=(0.0, 0.0, 0.0))


@pytest.fixture
def simple_atom_site():
    """Create a simple atom site for testing"""
    if not HAS_NUMPY:
        pytest.skip("numpy not available")
    from usif.structures.sites import AtomSite

    return AtomSite(atomic_number=14, coords=(0.0, 0.0, 0.0))


@pytest.fixture
def simple_structure():
    """Create a simple USIFStructure for testing"""
    if not HAS_NUMPY:
        pytest.skip("numpy not available")
    try:
        from usif import StructureProperties, USIFStructure, WyckoffSite

        return USIFStructure(
            structure_type=StructureType.CRYSTAL,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=np.eye(3) * 5.0,
            spacegroup=227,
            wyckoff_sites=[WyckoffSite(14, 8, (0.0, 0.0, 0.0))],
            structure_properties=StructureProperties(energy=-10.5, volume=125.0),
            formula="Si",
        )
    except ImportError:
        pytest.skip("Required dependencies not available")


@pytest.fixture
def encoder_gzip():
    """Create a USIF encoder with GZIP compression"""
    try:
        from usif import USIF

        return USIF(compression=CompressionType.GZIP)
    except ImportError:
        pytest.skip("Required dependencies not available")


@pytest.fixture
def encoder_none():
    """Create a USIF encoder without compression"""
    try:
        from usif import USIF

        return USIF(compression=CompressionType.NONE)
    except ImportError:
        pytest.skip("Required dependencies not available")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "requires_numpy: mark test as requiring numpy")
    config.addinivalue_line(
        "markers", "requires_pymatgen: mark test as requiring pymatgen"
    )
    config.addinivalue_line("markers", "requires_monty: mark test as requiring monty")
    config.addinivalue_line(
        "markers", "requires_deps: mark test as requiring all dependencies"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically skip tests based on available dependencies"""
    for item in items:
        # Skip if test requires numpy but it's not available
        if "requires_numpy" in [mark.name for mark in item.iter_markers()]:
            if not HAS_NUMPY:
                item.add_marker(pytest.mark.skip(reason="numpy not available"))

        # Skip if test requires pymatgen but it's not available
        if "requires_pymatgen" in [mark.name for mark in item.iter_markers()]:
            if not HAS_PYMATGEN:
                item.add_marker(pytest.mark.skip(reason="pymatgen not available"))

        # Skip if test requires monty but it's not available
        if "requires_monty" in [mark.name for mark in item.iter_markers()]:
            if not HAS_MONTY:
                item.add_marker(pytest.mark.skip(reason="monty not available"))

        # Skip if test requires all deps but any are missing
        if "requires_deps" in [mark.name for mark in item.iter_markers()]:
            if not (HAS_NUMPY and HAS_PYMATGEN and HAS_MONTY):
                item.add_marker(
                    pytest.mark.skip(reason="required dependencies not available")
                )
