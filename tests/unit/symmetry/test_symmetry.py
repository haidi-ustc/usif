"""Lossless asymmetric-unit reduction and expansion."""

import numpy as np
import pytest

from usif.codec.record import decode, encode_with_info
from usif.errors import FormatError, ValidationError
from usif.model import Cell, Structure
from usif.symmetry import SymmetricForm, analyze, expand, reduce

ROCKSALT = np.array(
    [
        [0, 0, 0],
        [0, 0.5, 0.5],
        [0.5, 0, 0.5],
        [0.5, 0.5, 0],
        [0.5, 0.5, 0.5],
        [0.5, 0, 0],
        [0, 0.5, 0],
        [0, 0, 0.5],
    ]
)
NACL_Z = [11] * 4 + [17] * 4


def nacl(shift=0.0, a=5.64) -> Structure:
    return Structure.from_fractional(NACL_Z, np.mod(ROCKSALT + shift, 1.0), Cell.cubic(a))


def round_trip(s: Structure) -> Structure:
    form = reduce(s)
    assert form is not None
    numbers, frac = expand(form)
    return Structure.from_fractional(numbers, frac, s.cell)


@pytest.mark.parametrize(
    "structure",
    [
        nacl(),
        nacl(shift=0.123),
        nacl().permute([7, 0, 6, 1, 5, 2, 4, 3]),
        Structure.from_fractional(
            NACL_Z * 2,
            np.vstack([ROCKSALT * [0.5, 1, 1], ROCKSALT * [0.5, 1, 1] + [0.5, 0, 0]]),
            Cell(np.diag([11.28, 5.64, 5.64])),
        ),
        Structure.from_fractional(
            [14] * 2,
            [[0, 0, 0], [0.25, 0.25, 0.25]],
            Cell([[0, 2.715, 2.715], [2.715, 0, 2.715], [2.715, 2.715, 0]]),
        ),
    ],
    ids=["conventional", "shifted-origin", "shuffled", "supercell-2x1x1", "si-primitive"],
)
def test_reduction_reproduces_structure_and_order(structure):
    out = round_trip(structure)
    assert np.array_equal(out.numbers, structure.numbers)
    assert np.allclose(out.positions, structure.positions, atol=1e-10)


def test_large_supercell_reduces_quickly():
    n = 6
    grid = np.array(np.meshgrid(*[range(n)] * 3)).reshape(3, -1).T
    frac = ((ROCKSALT[None] + grid[:, None]) / n).reshape(-1, 3)
    big = Structure.from_fractional(np.tile(NACL_Z, n**3), frac, Cell.cubic(5.64 * n))
    form = reduce(big)
    assert form is not None and len(form.numbers) == 2 and form.spacegroup == 225
    assert np.allclose(round_trip(big).positions, big.positions, atol=1e-9)


@pytest.mark.parametrize(
    "structure",
    [
        Structure(nacl().numbers, nacl().positions - [5.64, 0, 0], nacl().cell),
        Structure.from_fractional(
            np.random.default_rng(0).integers(1, 30, 60),
            np.random.default_rng(1).random((60, 3)),
            Cell.cubic(12.0),
        ),
        Structure(
            nacl().numbers,
            nacl().positions + np.random.default_rng(2).normal(scale=1e-3, size=(8, 3)),
            nacl().cell,
        ),
        Structure(nacl().numbers, nacl().positions, nacl().cell, pbc=(True, True, False)),
        Structure([8, 1, 1], [[0, 0, 0], [0.76, 0.59, 0], [-0.76, 0.59, 0]]),
    ],
    ids=["atom-outside-cell", "no-symmetry", "noisy", "slab", "molecule"],
)
def test_lossy_or_pointless_reductions_are_refused(structure):
    assert reduce(structure) is None


def test_per_atom_arrays_block_reduction():
    s = nacl()
    s.arrays["magmom"] = np.r_[np.ones(4), -np.ones(4)]
    assert reduce(s) is None


def test_analyze():
    info = analyze(nacl())
    assert info.number == 225 and info.symbol == "Fm-3m" and info.hall_number == 523
    with pytest.raises(ValidationError):
        analyze(Structure([1], [[0, 0, 0]]))


def test_form_validation():
    good = dict(
        hall_number=523,
        transformation=np.eye(3),
        origin_shift=np.zeros(3),
        numbers=[11],
        multiplicities=[4],
        positions=[[0, 0, 0]],
    )
    assert SymmetricForm(**good).natoms == 4
    for key, value in [
        ("hall_number", 0),
        ("transformation", np.zeros((3, 3))),
        ("multiplicities", [0]),
        ("positions", [[np.nan, 0, 0]]),
    ]:
        with pytest.raises(ValidationError):
            SymmetricForm(**{**good, key: value})
    with pytest.raises(ValidationError):
        SymmetricForm(**good, order=[0, 0, 1, 2])
    with pytest.raises(FormatError):
        expand(SymmetricForm(**{**good, "multiplicities": [3]}))


def test_tampered_symm_section_is_rejected():
    data, info = encode_with_info(nacl(), symmetry="auto", compression="none")
    assert info.symmetric
    raw = bytearray(data)
    hall_at = raw.index(b"SYMM") + 12
    raw[hall_at : hall_at + 2] = (1).to_bytes(2, "little")  # P1: multiplicities no longer match
    from usif.codec.record import HEADER_SIZE, _digest

    raw[32:40] = _digest(bytes(raw[HEADER_SIZE:]))
    with pytest.raises(FormatError):
        decode(bytes(raw))
