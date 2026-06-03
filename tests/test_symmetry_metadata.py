"""Tests for explicit symmetry reconstruction metadata."""

import numpy as np
from pymatgen.core import Lattice, Structure

from usif import USIF, CompressionType, StorageMode, StructureConverter, SymmetryMetadata
from usif.interop import PymatgenExporter, PymatgenImporter


def test_symmetry_metadata_roundtrips_through_binary_encoding():
    pmg = Structure(
        Lattice.cubic(5.43),
        ["Si", "Si"],
        [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )
    structure = StructureConverter.from_pymatgen(pmg, force_symmetric=True)

    metadata = structure.get_symmetry_metadata()
    assert isinstance(metadata, SymmetryMetadata)
    assert metadata.reconstruction_mode == "spacegroup_expansion"
    assert metadata.source_coordinate_frame == "fractional"

    encoder = USIF(compression=CompressionType.NONE)
    encoded = encoder.encode(structure)
    decoded, _ = encoder.decode(encoded)
    decoded_metadata = decoded.get_symmetry_metadata()

    assert decoded_metadata == metadata


def test_pymatgen_interop_wrappers_delegate_to_converter():
    pmg = Structure(
        Lattice.cubic(3.5),
        ["Na", "Cl"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )

    usif_structure = PymatgenImporter.from_pymatgen(pmg)
    assert usif_structure.storage_mode in (
        StorageMode.SYMMETRIC,
        StorageMode.FULL_ATOMIC,
    )

    roundtrip = PymatgenExporter.to_pymatgen(usif_structure)
    assert len(roundtrip) == len(pmg)
    assert np.isclose(roundtrip.lattice.a, pmg.lattice.a)
