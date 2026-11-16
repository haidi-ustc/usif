"""Structures, per-atom arrays, properties with units, and the .usif record format.

Shows the encoding options (compression, precision, symmetry) and what the
two identity hashes mean.
"""

import numpy as np

from usif import Cell, Structure
from usif.codec import decode, encode_with_info, jsondoc

ROCKSALT = [
    [0, 0, 0], [0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0],
    [0.5, 0.5, 0.5], [0.5, 0, 0], [0, 0.5, 0], [0, 0, 0.5],
]  # fmt: skip

# A structure is columns: numbers, Cartesian positions (float64), an optional cell.
nacl = Structure.from_fractional([11] * 4 + [17] * 4, ROCKSALT, Cell.cubic(5.64))
print(f"Structure: {nacl}  volume={nacl.volume:.2f} Å^3")

# Structure properties; built-in names get dtype, shape and default unit from the schema.
nacl.properties["energy"] = -27.2
nacl.properties["stress"] = np.eye(3) * 0.1  # 3x3 is stored in Voigt order
nacl.properties.set("pressure", 1.0e-4, unit="GPa")
nacl.properties["calculation"] = {"code": "VASP", "encut": 520}  # any JSON value
print(f"Units: {nacl.properties.units()}")

# Symmetric records store the asymmetric unit when that is lossless and smaller:
# here a 3x3x3 supercell (216 atoms) is stored as 2 atoms.
grid = np.array(np.meshgrid(*[range(3)] * 3)).reshape(3, -1).T
frac = ((np.array(ROCKSALT)[None] + grid[:, None]) / 3).reshape(-1, 3)
supercell = Structure.from_fractional(np.tile(nacl.numbers, 27), frac, Cell.cubic(3 * 5.64))
for options in ({}, {"symmetry": "auto"}, {"precision": "f32"}, {"compression": "lzma"}):
    data, info = encode_with_info(supercell, **options)
    print(f"{str(options):28} {len(data):6d} bytes  symmetric={info.symmetric}")

# Per-atom arrays (forces, charges, anything) are columns too.
rng = np.random.default_rng(0)
relaxed = nacl.copy()
relaxed.arrays["force"] = rng.normal(scale=0.01, size=(8, 3))
relaxed.arrays.set("charge", [0.8] * 4 + [-0.8] * 4, unit="e")

a = encode_with_info(nacl)[1]
b = encode_with_info(relaxed)[1]
print(f"Same geometry hash: {a.geometry_hash == b.geometry_hash}")
print(f"Record hashes differ: {a.record_hash != b.record_hash}")

data, _ = encode_with_info(relaxed)
print(f"Exact decode: {decode(data) == relaxed}")
print(f"JSON exact: {jsondoc.loads(jsondoc.dumps(relaxed)) == relaxed}")
