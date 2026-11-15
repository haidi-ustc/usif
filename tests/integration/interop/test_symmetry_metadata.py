"""Symmetry metadata and self-describing symmetric records."""

import numpy as np
import pytest

pytest.importorskip("pymatgen")

from usif import (
    USIF,
    AtomicProperties,
    AtomSite,
    CompressionType,
    StorageMode,
    StructureType,
    SymmetryMetadata,
    USIFStructure,
)
from usif.interop.pymatgen import PymatgenExporter, PymatgenImporter


def _si_conventional():
    from pymatgen.core import Lattice, Structure

    return Structure.from_spacegroup(227, Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])


def test_reduced_records_are_self_describing():
    structure = PymatgenImporter.from_pymatgen(_si_conventional(), force_symmetric=True)
    assert structure.storage_mode == StorageMode.SYMMETRIC
    # Format-6 symmetric records carry their exact spglib setting and are
    # lossless by construction, so no reconstruction metadata is attached.
    assert structure.get_symmetry_metadata() is None
    hall, P, p = structure.symmetry_setting()
    assert 1 <= hall <= 530 and P.shape == (3, 3) and p.shape == (3,)


def test_symmetry_metadata_roundtrips_through_binary_encoding():
    structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.eye(3) * 3.0,
        atom_sites=[AtomSite(1, (0.0, 0.0, 0.0), AtomicProperties())],
        formula="H2",
    )
    metadata = SymmetryMetadata(
        lossless=True,
        reconstruction_mode="spacegroup_expansion",
        symmetry_origin="user",
        source_coordinate_frame="fractional",
        tolerance=0.01,
    )
    structure.set_symmetry_metadata(metadata)

    encoder = USIF(compression=CompressionType.NONE)
    decoded, _ = encoder.decode(encoder.encode(structure))
    assert decoded.get_symmetry_metadata() == metadata


def test_pymatgen_interop_adapters_roundtrip():
    pmg = _si_conventional()
    usif_structure = PymatgenImporter.from_pymatgen(pmg)
    roundtrip = PymatgenExporter.to_pymatgen(usif_structure)
    assert len(roundtrip) == len(pmg)
    assert np.isclose(roundtrip.lattice.a, pmg.lattice.a)
    assert roundtrip.matches(pmg)
