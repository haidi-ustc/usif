"""Regression tests for reliability and defensive decoding fixes."""

import struct
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from usif import (
    USIF,
    CompressionType,
    ContainerIndexError,
    CorruptedDataError,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
    WyckoffSite,
)
from usif.storage import StructureContainer
from usif.constants import BinaryFormat
from usif.integrations.materials_project import load_mp_data_from_archive, safe_extract


def make_structure(energy=-1.0):
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, (0.0, 0.0, 0.0))],
        structure_properties=StructureProperties(energy=energy),
        formula="H",
    )


def test_decode_rejects_truncated_header():
    with pytest.raises(CorruptedDataError):
        USIF(compression=CompressionType.NONE).decode(b"USIF")


def test_decode_rejects_compressed_size_mismatch():
    encoder = USIF(compression=CompressionType.NONE)
    encoded = bytearray(encoder.encode(make_structure()))
    original_size = struct.unpack(BinaryFormat.UINT32, encoded[12:16])[0]
    encoded[12:16] = struct.pack(BinaryFormat.UINT32, original_size + 1)

    with pytest.raises(CorruptedDataError, match="Compressed payload size mismatch"):
        encoder.decode(bytes(encoded))


def test_decode_rejects_raw_size_mismatch():
    encoder = USIF(compression=CompressionType.NONE)
    encoded = bytearray(encoder.encode(make_structure()))
    original_size = struct.unpack(BinaryFormat.UINT32, encoded[8:12])[0]
    encoded[8:12] = struct.pack(BinaryFormat.UINT32, original_size + 1)

    with pytest.raises(CorruptedDataError, match="Raw payload size mismatch"):
        encoder.decode(bytes(encoded))


def test_decode_rejects_property_section_length_mismatch():
    encoder = USIF(compression=CompressionType.NONE)
    encoded = bytearray(encoder.encode(make_structure()))

    # Format 6, symmetric crystal in its default setting with one Wyckoff site:
    # props_len begins after type(1), mode(1), lattice(36), spacegroup(2),
    # hall(2), setting flags(1), site_count(4), site(Z 1 + mult 4 + xyz 12 + occ 4).
    props_len_offset = USIF.HEADER_SIZE + 1 + 1 + 36 + 2 + 2 + 1 + 4 + 21
    original_props_len = struct.unpack(
        BinaryFormat.UINT32, encoded[props_len_offset : props_len_offset + 4]
    )[0]
    encoded[props_len_offset : props_len_offset + 4] = struct.pack(
        BinaryFormat.UINT32, original_props_len + 1
    )

    with pytest.raises(CorruptedDataError, match="property section"):
        encoder.decode(bytes(encoded))


def test_safe_extract_rejects_zip_slip(tmp_path):
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.txt", "owned")
        zf.writestr("group_01/materials.json", "[]")

    with zipfile.ZipFile(archive, "r") as zf:
        with pytest.raises(ValueError, match="Unsafe zip member path"):
            safe_extract(zf, tmp_path / "out")

    assert not (tmp_path / "evil.txt").exists()


def test_safe_extract_rejects_zip_bomb_size_limits(tmp_path):
    archive = tmp_path / "too_large.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("group_01/materials.json", "[]")

    with zipfile.ZipFile(archive, "r") as zf:
        with pytest.raises(ValueError, match="expands beyond configured limit"):
            safe_extract(zf, tmp_path / "out", max_total_bytes=1)


def test_safe_extract_rejects_too_many_members(tmp_path):
    archive = tmp_path / "too_many.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("metadata.json", "{}")
        zf.writestr("group_01/materials.json", "[]")

    with zipfile.ZipFile(archive, "r") as zf:
        with pytest.raises(ValueError, match="too many members"):
            safe_extract(zf, tmp_path / "out", max_members=1)


def test_load_mp_archive_uses_safe_extract(tmp_path):
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("/absolute.txt", "owned")

    with pytest.raises(ValueError, match="Unsafe absolute zip member path"):
        load_mp_data_from_archive(archive, tmp_path / "out")


def test_concurrent_identical_add_deduplicates_once(tmp_path):
    path = tmp_path / "dedupe.usifc"
    structure = make_structure(energy=-1.0)

    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        with ThreadPoolExecutor(max_workers=32) as executor:
            hashes = list(executor.map(lambda _: container.add(structure), range(64)))

        assert len(set(hashes)) == 1
        assert len(container) == 1


def _read_header_index_offset(path):
    with open(path, "rb") as f:
        header = f.read(64)
    return struct.unpack(BinaryFormat.UINT64, header[20:28])[0]


def _corrupt_index_payload_byte(path, index_offset):
    header_size = struct.calcsize(StructureContainer.INDEX_HEADER_FORMAT)
    with open(path, "r+b") as f:
        f.seek(index_offset + header_size)
        b = f.read(1)
        assert b
        f.seek(index_offset + header_size)
        f.write(bytes([b[0] ^ 0xFF]))


def test_container_detects_corrupt_only_index_generation(tmp_path):
    path = tmp_path / "corrupt_index.usifc"
    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        container.add(make_structure(), name="first")

    index_offset = _read_header_index_offset(path)
    _corrupt_index_payload_byte(path, index_offset)

    with pytest.raises(ContainerIndexError):
        StructureContainer(path, mode="r", use_mmap=False)


def test_container_recovers_previous_valid_index_generation(tmp_path):
    path = tmp_path / "recover_index.usifc"
    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        container.add(make_structure(energy=-1.0), name="first")

    with StructureContainer(
        path, mode="a", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        container.add(make_structure(energy=-2.0), name="second")

    latest_index_offset = _read_header_index_offset(path)
    _corrupt_index_payload_byte(path, latest_index_offset)

    with StructureContainer(path, mode="r", use_mmap=False) as recovered:
        assert len(recovered) == 1
        assert recovered.get("first") is not None
        assert recovered.get("second") is None


def test_container_rejects_records_without_committed_index(tmp_path):
    path = tmp_path / "missing_index.usifc"
    with StructureContainer(
        path, mode="w", compression=CompressionType.NONE, use_mmap=False
    ) as container:
        container.add(make_structure(), name="first")

    with open(path, "r+b") as f:
        f.seek(20)
        f.write(struct.pack(BinaryFormat.UINT64, 0))

    with pytest.raises(ContainerIndexError, match="records but no committed index"):
        StructureContainer(path, mode="r", compression=CompressionType.NONE, use_mmap=False)
