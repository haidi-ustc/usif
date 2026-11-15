"""Format-5 records written by USIF 0.7.x must decode identically without pymatgen.

The fixtures in ``tests/fixtures/format5`` were produced by USIF 0.7.1 (the
pymatgen-based implementation). ``manifest.json`` records the atoms that its
pymatgen exporter reconstructed from each record, plus the stored hashes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from usif import USIF
from usif.storage import StructureContainer
from usif.symmetry.expand import expand_structure

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "format5"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())


@pytest.mark.parametrize("name", sorted(MANIFEST))
def test_format5_record_decodes_to_the_same_atoms(name):
    expected = MANIFEST[name]
    codec = USIF()
    structure, geometry_hash = codec.decode((FIXTURES / f"{name}.usif").read_bytes())

    assert geometry_hash.hex() == expected["geometry_hash"]
    assert structure.storage_mode.name == expected["storage_mode"]
    assert structure.formula == expected["formula"]
    assert codec.get_record_hash(structure) == expected["record_hash"]

    # Symmetric records do not carry atom order. 0.7.x sorted unwrapped
    # coordinates (so values like 0.99999999997 sorted last); 0.8 sorts wrapped
    # coordinates. Compare the reconstructed atoms as a set.
    full = expand_structure(structure)
    atoms = [(site.atomic_number, np.array(site.coords)) for site in full.atom_sites]
    assert len(atoms) == len(expected["atoms"])
    unmatched = [(z, np.array(c)) for z, c in expected["atoms"]]
    for z, coords in atoms:
        for index, (z_expected, coords_expected) in enumerate(unmatched):
            diff = coords - coords_expected
            if structure.is_crystal():
                diff -= np.round(diff)
            if z == z_expected and np.abs(diff).max() < 1e-6:
                unmatched.pop(index)
                break
        else:
            pytest.fail(f"{name}: atom Z={z} at {coords} not produced by format-5 reference")
    assert not unmatched


def test_format5_container_reads_validates_and_accepts_format6_appends(tmp_path):
    path = tmp_path / "mixed.usifc"
    shutil.copy(FIXTURES / "mixed.usifc", path)

    with StructureContainer(path, mode="r") as container:
        assert container.list_names() == ["fe_full_forces", "nacl_225", "rutile_136", "water_c2v"]
        assert container.get_structure_attributes("rutile_136") == {"case": "rutile_136"}
        result = container.validate(level="full")
        assert result.ok, result.errors
        rutile = container.get("rutile_136")

    with StructureContainer(path, mode="a") as container:
        new_hash = container.add(rutile, name="rutile_again")
        assert new_hash == container._name_index["rutile_136"]  # same record, deduplicated

        updated = rutile.copy()
        updated.structure_properties.energy = -2.5
        container.add(updated, name="rutile_v6")

    with StructureContainer(path, mode="r") as container:
        assert container.get("rutile_v6").structure_properties.energy == -2.5
        assert container.validate(level="full").ok
