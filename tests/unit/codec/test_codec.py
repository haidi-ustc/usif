"""Format-7 record codec, JSON document and wire primitives."""

import hashlib
import struct
import zlib

import numpy as np
import pytest

from usif.codec import compression, jsondoc
from usif.codec.record import (
    HEADER_SIZE,
    MAGIC,
    decode,
    decode_with_info,
    encode,
    encode_with_info,
    is_record,
    read_header,
)
from usif.codec.wire import ByteReader, ByteWriter
from usif.errors import ChecksumError, FormatError, UnsupportedVersionError, ValidationError
from usif.model import Cell, Structure

ROCKSALT = [
    [0, 0, 0],
    [0, 0.5, 0.5],
    [0.5, 0, 0.5],
    [0.5, 0.5, 0],
    [0.5, 0.5, 0.5],
    [0.5, 0, 0],
    [0, 0.5, 0],
    [0, 0, 0.5],
]


def nacl(**props) -> Structure:
    return Structure.from_fractional(
        [11] * 4 + [17] * 4, ROCKSALT, Cell.cubic(5.64), properties=props or None
    )


def rich() -> Structure:
    rng = np.random.default_rng(7)
    s = Structure(
        rng.integers(1, 90, 50),
        rng.random((50, 3)) * 10,
        Cell(np.diag([10.0, 11.0, 12.0]), pbc=(True, True, False)),
    )
    s.arrays["force"] = rng.normal(size=(50, 3))
    s.arrays.set("charge", rng.normal(size=50), unit="e")
    s.arrays["tag"] = np.arange(50, dtype=np.int16)
    s.arrays["fixed"] = rng.random(50) > 0.5
    s.arrays["label"] = [f"a{i}" for i in range(50)]
    s.properties["energy"] = -123.456789012345
    s.properties["stress"] = np.arange(6.0)
    s.properties["meta"] = {"code": "VASP", "nested": {"k": [1, 2.5, None, True]}, "ü": "ß"}
    s.properties["kpts"] = np.array([4, 4, 2], dtype=np.uint32)
    return s


def build_record(payload: bytes, *, compression_id: int = 0, version: int = 7, flags: int = 0):
    stored = zlib.compress(payload) if compression_id == 1 else payload
    header = (
        MAGIC
        + struct.pack(
            "<HHB3sQQ", version, flags, compression_id, b"\0\0\0", len(payload), len(stored)
        )
        + hashlib.blake2b(stored, digest_size=8).digest()
    )
    return header + stored


def section(tag: bytes, body: bytes) -> bytes:
    return tag + struct.pack("<Q", len(body)) + body


def payload_of(structure: Structure, **options) -> bytes:
    data = encode(structure, compression="none", **options)
    return data[HEADER_SIZE:]


class TestRoundTrip:
    @pytest.mark.parametrize("codec", ["none", "zlib", "lzma"])
    def test_exact_round_trip(self, codec):
        s = rich()
        out = decode(encode(s, compression=codec))
        assert out == s
        assert out.arrays.unit("charge") == "e"
        assert out.arrays.dtype("tag") == np.dtype("int16").str
        assert out.properties["meta"]["ü"] == "ß"

    def test_molecule_round_trip(self):
        water = Structure([8, 1, 1], [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]])
        assert decode(encode(water)) == water

    def test_f32_precision_is_compact_and_close(self):
        s = rich()
        small = encode(s, precision="f32", compression="none")
        assert len(small) < len(encode(s, compression="none"))
        assert decode(small).allclose(s, atol=1e-5)

    def test_symmetric_round_trip_keeps_order(self):
        s = nacl().permute([3, 6, 0, 7, 1, 5, 2, 4])
        s.properties["energy"] = -1.0
        data, info = encode_with_info(s, symmetry="auto", compression="none")
        assert info.symmetric
        out = decode(data)
        assert np.array_equal(out.numbers, s.numbers)
        assert out.allclose(s, atol=1e-10)
        assert len(data) < len(encode(s, compression="none"))

    def test_symmetry_is_skipped_with_per_atom_arrays(self):
        s = nacl()
        s.arrays["magmom"] = np.r_[np.ones(4), -np.ones(4)]
        assert not encode_with_info(s, symmetry="auto")[1].symmetric

    def test_bad_options(self):
        with pytest.raises(ValidationError):
            encode(nacl(), precision="f16")
        with pytest.raises(ValidationError):
            encode(nacl(), symmetry="always")
        with pytest.raises(ValidationError):
            encode(nacl(), compression="snappy")
        with pytest.raises(ValidationError):
            encode("not a structure")


class TestIdentity:
    def test_encoding_is_deterministic(self):
        assert encode(rich()) == encode(rich())

    def test_hashes_do_not_depend_on_compression(self):
        a = encode_with_info(rich(), compression="none")[1]
        b = encode_with_info(rich(), compression="lzma")[1]
        assert (a.record_hash, a.geometry_hash) == (b.record_hash, b.geometry_hash)

    def test_geometry_hash_ignores_properties(self):
        a = encode_with_info(nacl(energy=-1.0))[1]
        b = encode_with_info(nacl(energy=-2.0))[1]
        assert a.geometry_hash == b.geometry_hash
        assert a.record_hash != b.record_hash

    def test_decode_reports_same_info(self):
        data, info = encode_with_info(rich(), symmetry="auto")
        assert decode_with_info(data)[1] == info


class TestIntegrity:
    def test_header_is_parsed(self):
        data = encode(nacl(), compression="zlib")
        header = read_header(data)
        assert header.compression == 1 and header.record_size == len(data)
        assert is_record(data) and not is_record(b"USIF\0\0\0\x06")

    def test_bit_flip_is_detected_before_decompression(self):
        data = bytearray(encode(rich()))
        data[HEADER_SIZE + 10] ^= 0x01
        with pytest.raises(ChecksumError):
            decode(bytes(data))

    @pytest.mark.parametrize("cut", [0, 5, HEADER_SIZE - 1, HEADER_SIZE + 3])
    def test_truncation(self, cut):
        data = encode(rich())
        with pytest.raises(FormatError):
            decode(data[:cut])

    def test_trailing_bytes(self):
        with pytest.raises(FormatError):
            decode(encode(nacl()) + b"\0")

    def test_size_limit(self):
        with pytest.raises(FormatError, match="exceeds limit"):
            decode(encode(rich()), max_size=100)

    def test_lying_raw_size_is_rejected(self):
        payload = payload_of(nacl())
        stored = zlib.compress(payload + b"\0" * 10_000)
        header = (
            MAGIC
            + struct.pack("<HHB3sQQ", 7, 0, 1, b"\0\0\0", len(payload), len(stored))
            + hashlib.blake2b(stored, digest_size=8).digest()
        )
        with pytest.raises(FormatError, match="larger than declared"):
            decode(header + stored)

    @pytest.mark.parametrize(
        "version, flags, error",
        [
            (6, 0, UnsupportedVersionError),
            (8, 0, UnsupportedVersionError),
            (7, 1, UnsupportedVersionError),
        ],
    )
    def test_header_fields(self, version, flags, error):
        with pytest.raises(error):
            decode(build_record(payload_of(nacl()), version=version, flags=flags))

    def test_unknown_compression(self):
        with pytest.raises(FormatError):
            decode(build_record(payload_of(nacl()), compression_id=99))

    def test_unknown_critical_section_is_rejected(self):
        with pytest.raises(FormatError, match="critical"):
            decode(build_record(payload_of(nacl()) + section(b"XTRA", b"1234")))

    def test_ancillary_section_is_skipped(self):
        s = nacl()
        out = decode(build_record(payload_of(s) + section(b"xtra", b"anything")))
        assert out == s

    def test_section_order_and_duplicates(self):
        payload = payload_of(nacl(energy=1.0))
        reader = ByteReader(payload)
        parts = []
        while reader.remaining:
            tag = bytes(reader.raw(4, "tag"))
            body = bytes(reader.raw(reader.u64("size"), "body"))
            parts.append(section(tag, body))
        with pytest.raises(FormatError, match="order"):
            decode(build_record(b"".join([parts[1], parts[0], *parts[2:]])))
        with pytest.raises(FormatError, match="duplicate"):
            decode(build_record(b"".join(parts + parts[-1:])))
        with pytest.raises(FormatError, match="ATOM"):
            decode(build_record(b"".join(parts[1:])))

    def test_invalid_atomic_numbers_in_record(self):
        body = struct.pack("<I", 1) + bytes([200])
        posn = bytes([11]) + struct.pack("<3d", 0, 0, 0)
        with pytest.raises(FormatError):
            decode(build_record(section(b"ATOM", body) + section(b"POSN", posn)))

    def test_column_lies_about_its_size(self):
        bad = ByteWriter()
        bad.u32(1)
        bad.string("x")
        bad.string("")
        bad.u8(11)
        bad.u8(1)
        bad.u64(10**12)
        payload = payload_of(nacl()) + section(b"PROP", bad.getvalue())
        with pytest.raises(FormatError, match="more data"):
            decode(build_record(payload))


def column_block(name, unit, code, body):
    w = ByteWriter()
    w.u32(1)
    w.string(name)
    w.string(unit)
    w.u8(code)
    return w.getvalue() + body


def molecule_payload() -> bytes:
    atom = struct.pack("<I", 1) + bytes([1])
    posn = bytes([11]) + struct.pack("<3d", 0, 0, 0)
    return section(b"ATOM", atom) + section(b"POSN", posn)


class TestWireTypes:
    """Each field has one wire type, and decoding accepts only canonical bytes."""

    @pytest.mark.parametrize(
        "options",
        [{}, {"precision": "f32"}, {"symmetry": "auto"}, {"compression": "lzma"}],
        ids=str,
    )
    @pytest.mark.parametrize("make", [nacl, rich], ids=["nacl", "rich"])
    def test_reencoding_a_decoded_record_gives_the_same_bytes(self, make, options):
        data = encode(make(), **options)
        assert encode(decode(data), **options) == data

    def test_field_sizes(self):
        s = nacl()
        payload = payload_of(s)
        atom = 4 + 8 + 4 + 8  # tag, size, u32 count, u8[8]
        cell = 4 + 8 + 1 + 72  # tag, size, u8 pbc, f64[3][3]
        posn = 4 + 8 + 1 + 8 * 24  # tag, size, u8 dtype, f64[8][3]
        assert len(payload) == atom + cell + posn
        f32 = payload_of(s, precision="f32")
        assert len(payload) - len(f32) == 4 * 24

    def test_decoded_types(self):
        s = decode(encode(rich(), precision="f32"))
        assert s.numbers.dtype == np.uint8
        assert s.positions.dtype == np.float64 and s.cell.matrix.dtype == np.float64
        assert s.arrays.dtype("tag") == "<i2" and s.properties.dtype("kpts") == "<u4"
        assert s.arrays.dtype("fixed") == "|b1" and s.arrays.dtype("label") == "json"
        assert not s.positions.flags.writeable

    def test_f32_overflow_is_refused(self):
        s = Structure([1], [[1e39, 0, 0]])
        with pytest.raises(ValidationError, match="overflow"):
            encode(s, precision="f32")

    def test_non_canonical_unit_is_rejected(self):
        body = struct.pack("<B", 0) + struct.pack("<d", 1.0)
        payload = molecule_payload() + section(b"PROP", column_block("x", "Ang", 11, body))
        with pytest.raises(FormatError, match="normalised"):
            decode(build_record(payload))

    @pytest.mark.parametrize("text", [b'{"b":1, "a":2}', b'{"b":1,"a":2}', b"1.00"])
    def test_non_canonical_json_is_rejected(self, text):
        body = struct.pack("<Q", len(text)) + text
        payload = molecule_payload() + section(b"PROP", column_block("x", "", 0, body))
        with pytest.raises(FormatError, match="canonical"):
            decode(build_record(payload))

    def test_schema_dtype_mismatch_is_rejected(self):
        body = struct.pack("<B", 0) + struct.pack("<f", -1.5)  # energy as float32
        payload = molecule_payload() + section(b"PROP", column_block("energy", "eV", 10, body))
        with pytest.raises(FormatError, match="schema keeps it"):
            decode(build_record(payload))

    def test_invalid_cell_in_record(self):
        atom = struct.pack("<I", 1) + bytes([1])
        cell = bytes([7]) + struct.pack("<9d", *([0.0] * 9))
        posn = bytes([11]) + struct.pack("<3d", 0, 0, 0)
        payload = section(b"ATOM", atom) + section(b"CELL", cell) + section(b"POSN", posn)
        with pytest.raises(FormatError, match="invalid cell"):
            decode(build_record(payload))

    def test_wide_atom_order_for_a_small_structure_is_rejected(self):
        s = nacl()
        shuffled = s.replace(numbers=s.numbers[::-1].copy(), positions=s.positions[::-1].copy())
        payload = payload_of(shuffled, symmetry="auto")
        if b"SYMM" not in payload:
            pytest.skip("structure was not stored symmetrically")
        index = payload.index(b"SYMM") + 12
        body = bytearray(payload[index:])
        width_at = len(body) - 8 * 2 - 1
        assert body[width_at] == 2
        order = struct.unpack("<8H", bytes(body[width_at + 1 :]))
        body = body[:width_at] + bytes([4]) + struct.pack("<8I", *order)
        new = payload[: index - 8] + struct.pack("<Q", len(body)) + bytes(body)
        with pytest.raises(FormatError, match="4-byte"):
            decode(build_record(new))


class TestJson:
    def test_exact_round_trip(self):
        s = rich()
        assert jsondoc.loads(jsondoc.dumps(s)) == s
        water = Structure([8, 1, 1], [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]])
        assert jsondoc.loads(jsondoc.dumps(water, indent=None)) == water

    @pytest.mark.parametrize(
        "text",
        [
            "[]",
            '{"schema": "usif.structure.json.v1"}',
            '{"schema": "usif.structure.json.v2", "numbers": [1]}',
            '{"schema": "usif.structure.json.v2", "numbers": [1], "positions": [[0,0,0]],'
            ' "properties": {"e": {"dtype": "object", "value": 1}}}',
            "{not json",
        ],
    )
    def test_rejects_bad_documents(self, text):
        with pytest.raises(FormatError):
            jsondoc.loads(text)


class TestCompressionAndWire:
    def test_registry(self):
        assert {"none", "zlib", "lzma", "zstd"} <= set(compression.available())
        with pytest.raises(ValidationError):
            compression.register(compression.Compressor(1, "dup", lambda d, l: d, lambda d, n: d))

    def test_reader_bounds(self):
        reader = ByteReader(b"\x01\x02")
        assert reader.u8("a") == 1
        with pytest.raises(FormatError):
            reader.u16("b")
        with pytest.raises(FormatError):
            ByteReader(b"\x05\x00ab").string("s")
