"""Export the result of a dataset query to one structure file (``usif dataset export``).

The selection is a query (``--group``, ``--formula``, ``--elements``, ``--prop``, ``--limit``)
or a list of ``--entry`` paths; entries are written in dataset order. An existing file is
never replaced without ``--overwrite``, and nothing is written when no entry matches. Several
structures need a multi-frame format such as extxyz (written through ASE); one structure can
also go to ``.usif`` or ``.json``.
"""

import contextlib
import importlib.util
import io
import tempfile
from pathlib import Path

import usif
from usif.cli import main


def salt(symbols, a, energy):
    return usif.Structure.from_fractional(
        symbols, [[0, 0, 0], [0.5, 0.5, 0.5]], usif.Cell.cubic(a), properties={"energy": energy}
    )


def usif_cli(*argv):
    print(f"$ usif {' '.join(map(str, argv))}")
    errors = io.StringIO()
    with contextlib.redirect_stderr(errors):
        code = main([str(a) for a in argv])
    print(errors.getvalue(), end="")
    return code


with tempfile.TemporaryDirectory() as tmp:
    dataset = Path(tmp) / "salts.usifc"
    with usif.Dataset(dataset, "w") as data:
        data.add(salt(["Na", "Cl"], 5.64, -6.8), "NaCl", "/salts/rocksalt")
        data.add(salt(["K", "Cl"], 6.29, -6.5), "KCl", "/salts/rocksalt")
        data.add(salt(["Cs", "Cl"], 4.12, -6.1), "CsCl", "/salts/cscl")

    one = Path(tmp) / "nacl.json"
    assert usif_cli("dataset", "export", dataset, one, "--entry", "/salts/rocksalt/NaCl") == 0
    print(f"Read back: {usif.read(one).reduced_formula}")
    code = usif_cli("dataset", "export", dataset, one, "--formula", "KCl")
    print(f"Existing file refused: exit {code}")
    assert usif_cli("dataset", "export", dataset, one, "--formula", "KCl", "--overwrite") == 0
    print(f"Replaced with --overwrite: {usif.read(one).reduced_formula}")
    code = usif_cli("dataset", "export", dataset, Path(tmp) / "none.json", "--formula", "LiF")
    print(f"No match, nothing written: exit {code}")

    if importlib.util.find_spec("ase") is None:
        print("ASE is not installed: multi-frame export skipped")
    else:
        frames = Path(tmp) / "rocksalt.extxyz"
        query = ("--group", "/salts/rocksalt", "--prop", "energy<-6")
        assert usif_cli("dataset", "export", dataset, frames, *query) == 0
        print(f"Frames read back: {[s.reduced_formula for s in usif.read_all(frames)]}")
