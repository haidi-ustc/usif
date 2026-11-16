"""Generate format-6 / container-v2 golden fixtures with the USIF 0.8.0 code.

Usage: python -I gen_format6.py <old08-dir> <out-dir>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

import numpy as np  # noqa: E402

from usif.constants import StorageMode, StructureType  # noqa: E402
from usif.encoder import USIF  # noqa: E402
from usif.properties.atomic import AtomicProperties  # noqa: E402
from usif.properties.structure import StructureProperties  # noqa: E402
from usif.services.optimizer import optimize_structure  # noqa: E402
from usif.storage import StructureContainer  # noqa: E402
from usif.structures.sites import AtomSite  # noqa: E402
from usif.structures.structure import USIFStructure  # noqa: E402
from usif.symmetry.expand import expand_structure  # noqa: E402
from usif.version import __version__  # noqa: E402

assert __version__ == "0.8.0", __version__

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


def crystal(numbers, frac, lattice, props=None, sprops=None):
    sites = [
        AtomSite(int(z), tuple(float(c) for c in x), (props or {}).get(i, AtomicProperties()))
        for i, (z, x) in enumerate(zip(numbers, frac))
    ]
    return USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.FULL_ATOMIC,
        lattice_matrix=np.asarray(lattice, dtype=float),
        spacegroup=1,
        atom_sites=sites,
        structure_properties=sprops or StructureProperties(),
    )


def molecule(numbers, cart, props=None, sprops=None):
    sites = [
        AtomSite(int(z), tuple(float(c) for c in x), (props or {}).get(i, AtomicProperties()))
        for i, (z, x) in enumerate(zip(numbers, cart))
    ]
    return USIFStructure(
        structure_type=StructureType.MOLECULE,
        storage_mode=StorageMode.FULL_ATOMIC,
        atom_sites=sites,
        structure_properties=sprops or StructureProperties(),
    )


cases = {}

# Full-atomic crystal with every builtin atomic property, custom per-atom data and units.
rng = np.random.default_rng(5)
props = {
    i: AtomicProperties(
        force=tuple(float(v) for v in rng.normal(size=3)),
        charge=float(rng.normal()),
        magmom=float(i % 2),
        velocity=tuple(float(v) for v in rng.normal(size=3)),
        custom={"tag": f"atom{i}", "flags": [i, i + 1]},
    )
    for i in range(8)
}
sprops = StructureProperties(
    energy=-27.123456789,
    stress=(1.0, 2.0, 3.0, 0.1, 0.2, 0.3),
    pressure=0.5,
    temperature=300.0,
    custom={"code": "VASP", "params": {"encut": 520, "kpts": [4, 4, 4]}, "converged": True},
)
cases["nacl_full_props"] = crystal(
    [11] * 4 + [17] * 4,
    np.asarray(ROCKSALT) + rng.normal(scale=0.01, size=(8, 3)),
    np.diag([5.64, 5.65, 5.66]),
    props,
    sprops,
)

# Atoms with different property sets (only some carry a charge / custom value).
partial = {
    0: AtomicProperties(charge=0.5, custom={"note": "first"}),
    2: AtomicProperties(charge=-0.5),
}
cases["partial_props"] = crystal(
    [26, 8, 8], [[0, 0, 0], [0.25, 0.25, 0.25], [0.75, 0.75, 0.75]], np.eye(3) * 4.1, partial
)

# Symmetric crystals: default setting, shifted origin (p != 0), and a supercell (P != I).
cases["nacl_sym"] = optimize_structure(crystal([11] * 4 + [17] * 4, ROCKSALT, np.eye(3) * 5.64))
shifted = np.mod(np.asarray(ROCKSALT) + [0.1, 0.2, 0.3], 1.0)
cases["nacl_sym_shifted"] = optimize_structure(
    crystal([11] * 4 + [17] * 4, shifted, np.eye(3) * 5.64)
)
half = np.asarray(ROCKSALT) * [0.5, 1, 1]
cases["nacl_sym_supercell"] = optimize_structure(
    crystal(
        [11] * 4 + [17] * 4 + [11] * 4 + [17] * 4,
        np.vstack([half, half + [0.5, 0, 0]]),
        np.diag([11.28, 5.64, 5.64]),
    )
)
rutile = [
    [0, 0, 0],
    [0.5, 0.5, 0.5],
    [0.3, 0.3, 0],
    [0.7, 0.7, 0],
    [0.8, 0.2, 0.5],
    [0.2, 0.8, 0.5],
]
cases["rutile_sym_shifted"] = optimize_structure(
    crystal(
        [22, 22, 8, 8, 8, 8], np.mod(np.asarray(rutile) + 0.1, 1.0), np.diag([4.59, 4.59, 2.96])
    )
)
assert cases["rutile_sym_shifted"].origin_shift is not None
cases["nacl_sym_energy"] = optimize_structure(
    crystal(
        [11] * 4 + [17] * 4, ROCKSALT, np.eye(3) * 5.64, sprops=StructureProperties(energy=-3.5)
    )
)

# Molecule (always full-atomic in 0.8) with properties.
cases["water_props"] = molecule(
    [8, 1, 1],
    [[0, 0, 0.1173], [0, 0.7572, -0.4692], [0, -0.7572, -0.4692]],
    {
        0: AtomicProperties(charge=-0.8, force=(0.0, 0.0, 0.01)),
        1: AtomicProperties(charge=0.4, force=(0.0, 0.01, 0.0)),
        2: AtomicProperties(charge=0.4, force=(0.0, -0.01, 0.0)),
    },
    StructureProperties(energy=-14.22, custom={"method": "PBE"}),
)

from usif.constants import CompressionType  # noqa: E402

codecs = {
    True: USIF(compression=CompressionType.GZIP),
    False: USIF(compression=CompressionType.NONE),
}
codec = codecs[True]
manifest = {}
for name, structure in cases.items():
    data = codecs[name.endswith("props")].encode(structure)
    (OUT / f"{name}.usif").write_bytes(data)
    decoded, geometry_hash = codec.decode(data)
    full = expand_structure(decoded) if decoded.storage_mode == StorageMode.SYMMETRIC else decoded
    entry = {
        "storage_mode": decoded.storage_mode.name,
        "record_hash": codec.get_record_hash(decoded),
        "geometry_hash": geometry_hash.hex(),
        "decoded": decoded.as_dict(),
        "expanded_atoms": [[s.atomic_number, list(map(float, s.coords))] for s in full.atom_sites],
    }
    manifest[name] = entry
    print(name, decoded.storage_mode.name, len(data), "bytes", len(full.atom_sites), "atoms")

# A v2 container: groups, attributes, a duplicate and a removal-free history.
container_path = OUT / "container_v2.usifc"
if container_path.exists():
    container_path.unlink()
with StructureContainer(container_path, mode="w") as c:
    c.add(
        cases["nacl_full_props"],
        name="nacl_full",
        group="/train",
        attributes={"split": "train", "id": 1},
    )
    c.add(
        cases["water_props"], name="water", group="/train/molecules", attributes={"split": "train"}
    )
    c.add(
        cases["nacl_sym"], name="nacl_sym", group="/test", attributes={"split": "test", "ok": True}
    )
    c.add(cases["nacl_sym_supercell"], name="nacl_super", group="/test")
    c.add(cases["nacl_sym"], name="nacl_sym_again", group="/")
    c.add(cases["partial_props"])  # unnamed
    c.set_group_attribute("/train", "description", "training set")
with StructureContainer(container_path, mode="r") as c:
    manifest["__container__"] = {
        "names": c.list_names(),
        "groups": c.list_groups(),
        "stats": {k: v for k, v in c.stats().items() if isinstance(v, (int, str, float))},
        "attributes": {n: c.get_structure_attributes(n) for n in c.list_names()},
        "group_attributes": {"/train": c.get_group_attribute("/train", "description")},
    }
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
print(json.dumps(manifest["__container__"], indent=1, default=str)[:1500])
