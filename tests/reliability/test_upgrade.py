"""Reading files written by USIF 0.8 and earlier (record formats 5/6, container v2).

The fixtures were produced by the real 0.7.1 (``tests/fixtures/format5``) and
0.8.0 (``tests/fixtures/format6``, see ``generate.py``) implementations.
"""

import json
import shutil
import struct
import warnings
from pathlib import Path

import numpy as np
import pytest

from usif.dataset import Dataset, Q
from usif.errors import ChecksumError, FormatError
from usif.upgrade import is_container_v2, is_format6, open_container_v2
from usif.upgrade.format6 import decode, decode_with_info

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FORMAT5 = json.loads((FIXTURES / "format5" / "manifest.json").read_text())
FORMAT6 = json.loads((FIXTURES / "format6" / "manifest.json").read_text())
FORMAT6_RECORDS = sorted(k for k in FORMAT6 if not k.startswith("__"))


def read(directory: str, name: str) -> bytes:
    return (FIXTURES / directory / f"{name}.usif").read_bytes()


def frac_or_cart(structure):
    return structure.frac_positions if structure.cell is not None else structure.positions


def decode_quiet(data):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return decode_with_info(data)


@pytest.mark.parametrize("name", sorted(FORMAT5))
def test_format5_records_decode_to_reference_atoms(name):
    expected = FORMAT5[name]
    structure, info = decode_with_info(read("format5", name))
    assert info.version == 5 and info.geometry_hash == expected["geometry_hash"]
    assert info.symmetric == (expected["storage_mode"] == "SYMMETRIC")
    assert structure.reduced_formula == expected["formula"]
    # 0.7 sorted unwrapped coordinates, so compare as a set (as the 0.8 test did).
    unmatched = [(z, np.array(c)) for z, c in expected["atoms"]]
    for z, coords in zip(structure.numbers, frac_or_cart(structure)):
        for index, (z_ref, c_ref) in enumerate(unmatched):
            diff = coords - c_ref
            if structure.cell is not None:
                diff -= np.round(diff)
            if z == z_ref and np.abs(diff).max() < 1e-6:
                unmatched.pop(index)
                break
        else:
            pytest.fail(f"{name}: atom Z={z} at {coords} not in the reference")
    assert not unmatched
    assert "__usif_symmetry_metadata__" not in structure.properties


@pytest.mark.parametrize("name", FORMAT6_RECORDS)
def test_format6_records_match_0_8_decoding(name):
    expected = FORMAT6[name]
    structure, info = decode_quiet(read("format6", name))
    assert info.version == 6 and info.geometry_hash == expected["geometry_hash"]
    assert info.symmetric == (expected["storage_mode"] == "SYMMETRIC")
    reference = expected["expanded_atoms"]
    assert structure.numbers.tolist() == [z for z, _ in reference]
    np.testing.assert_allclose(
        frac_or_cart(structure), [c for _, c in reference], rtol=0, atol=1e-6
    )
    decoded = expected["decoded"]
    props = decoded["structure_properties"]
    for key in ("energy", "pressure", "temperature"):
        if props.get(key) is not None:
            assert structure.properties[key] == props[key]
            assert structure.properties.unit(key) == props["units"][key]
    if props.get("stress") is not None:
        np.testing.assert_array_equal(structure.properties["stress"], props["stress"])
    for key, value in props["custom"].items():
        assert structure.properties[key] == value
    for i, site in enumerate(decoded.get("atom_sites") or []):
        atom = site["properties"]
        for key in ("force", "charge", "magmom", "velocity"):
            if atom[key] is not None:
                np.testing.assert_array_equal(structure.arrays[key][i], atom[key])
                assert structure.arrays.unit(key) == atom["units"][key]
        for key, value in atom["custom"].items():
            assert np.asarray(structure.arrays[key][i]).tolist() == value


def test_partial_per_atom_builtin_gets_a_mask():
    with pytest.warns(UserWarning, match="charge_present"):
        structure = decode(read("format6", "partial_props"))
    assert structure.arrays["charge"].tolist() == [0.5, 0.0, -0.5]
    assert structure.arrays["charge_present"].tolist() == [True, False, True]
    assert structure.arrays["note"] == ["first", None, None]


def test_settings_are_honoured():
    supercell, info = decode_with_info(read("format6", "nacl_sym_supercell"))
    assert info.symmetric and supercell.natoms == 16
    rutile = FORMAT6["rutile_sym_shifted"]["decoded"]
    assert any(rutile["origin_shift"])
    assert decode(read("format6", "rutile_sym_shifted")).natoms == 6


class TestCorruption:
    def test_detection(self):
        data = read("format6", "nacl_full_props")
        assert is_format6(data) and not is_format6(b"\x89USIF\r\n\x1a")

    def test_geometry_bit_flip_in_uncompressed_record(self):
        data = bytearray(read("format6", "nacl_sym"))
        data[64 + 2 + 4] ^= 0x10  # inside the lattice
        with pytest.raises(ChecksumError, match="geometry hash"):
            decode(bytes(data))

    def test_gzip_bit_flip(self):
        data = bytearray(read("format6", "nacl_full_props"))
        data[200] ^= 0xFF
        with pytest.raises((ChecksumError, FormatError)):
            decode(bytes(data))

    def test_truncated_and_bad_header(self):
        data = read("format6", "nacl_sym")
        with pytest.raises(FormatError):
            decode(data[:-1])
        with pytest.raises(FormatError):
            decode(data[:10])
        with pytest.raises(FormatError):
            decode(data[:7] + b"\x09" + data[8:])
        bad = bytearray(data)
        bad[16] = 7  # compression type
        with pytest.raises(FormatError):
            decode(bytes(bad))

    def test_lying_raw_size(self):
        data = bytearray(read("format6", "nacl_full_props"))
        struct.pack_into("<I", data, 8, 10)
        with pytest.raises(FormatError):
            decode(bytes(data))


class TestContainerV2:
    def test_entries_groups_and_attributes(self):
        path = FIXTURES / "format6" / "container_v2.usifc"
        assert is_container_v2(path) and not is_container_v2(FIXTURES / "format6" / "manifest.json")
        reference = FORMAT6["__container__"]
        with open_container_v2(path) as container:
            assert not container.recovered
            named = {e.name: e for e in container if e.name}
            assert sorted(named) == reference["names"]
            for name, attrs in reference["attributes"].items():
                assert named[name].attrs == (attrs or {})
            assert named["water"].group == "/train/molecules"
            assert container.group_attrs["/train"] == {"description": "training set"}
            unnamed = [e for e in container if e.name is None]
            assert len(unnamed) == 1 and unnamed[0].group == "/"
            assert len(container.records) == reference["stats"]["records"]

    def test_recovers_from_bad_header_offset(self, tmp_path):
        path = tmp_path / "c.usifc"
        shutil.copy(FIXTURES / "format6" / "container_v2.usifc", path)
        with open(path, "r+b") as handle:
            handle.seek(20)
            handle.write(struct.pack("<Q", 999_999))
        with open_container_v2(path) as container:
            assert container.recovered and len(container) == 6

    def test_corrupted_index_is_rejected(self, tmp_path):
        path = tmp_path / "c.usifc"
        data = bytearray((FIXTURES / "format6" / "container_v2.usifc").read_bytes())
        index = data.rindex(b"USIFIDX2")
        data[index + 40] ^= 0xFF
        path.write_bytes(bytes(data))
        with pytest.raises(FormatError, match="no valid index"):
            open_container_v2(path)

    @pytest.mark.parametrize(
        "source, expected",
        [("format6/container_v2.usifc", 6), ("format5/mixed.usifc", 4)],
    )
    def test_import_into_dataset(self, tmp_path, source, expected):
        with Dataset(tmp_path / "new.usifc") as ds, warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert ds.import_v2(FIXTURES / source, group="/old") == expected
            assert len(ds) == expected
            assert ds.check(full=True).ok
        with Dataset(tmp_path / "new.usifc", "r") as ds:
            if source.startswith("format6"):
                assert ds.entry("/old/train/nacl_full").attrs == {"split": "train", "id": 1}
                assert ds.group_attrs("/old/train") == {"description": "training set"}
                assert ds.count(Q.group("/old/test")) == 2
                assert ds.stats()["records"] == 5  # nacl_sym shared by two entries
                water = ds["/old/train/molecules/water"]
                assert water.arrays.unit("charge") == "e" and water.properties["method"] == "PBE"
            else:
                assert ds.count(Q.group("/old/golden")) == 4
                assert ds["/old/golden/fe_full_forces"].arrays["force"].shape == (2, 3)

    def test_failed_import_leaves_dataset_unchanged(self, tmp_path):
        bad = tmp_path / "bad.usifc"
        source = FIXTURES / "format5" / "mixed.usifc"
        with open_container_v2(source) as container:
            entries = list(container)
            start, size = container.records[entries[-1].record_hash]
        data = bytearray(source.read_bytes())
        data[start + 64 + (size - 64) // 2] ^= 0xFF  # inside the last record's payload
        bad.write_bytes(bytes(data))
        with Dataset(tmp_path / "new.usifc") as ds:
            ds.add(decode(read("format5", "nacl_225")), "keep")
            with pytest.raises(FormatError):
                ds.import_v2(bad)
            assert len(ds) == 1
