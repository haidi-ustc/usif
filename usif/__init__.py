"""USIF: exact, compact, queryable storage for atomistic structures.

Core objects::

    from usif import Structure, Cell, read, write, convert, Dataset, Q

    s = read("POSCAR")                      # any backend format, .usif or .json
    write(s, "s.usif", symmetry="auto")     # format-7 record
    with Dataset("data.usifc") as ds:       # SQLite-backed collection
        ds.add(s, "relaxed", "/runs")
        hits = list(ds.query(Q.formula("NaCl") & (Q.prop("energy") < 0)))

``Dataset``/``Q`` and the backends are imported on first use.
"""

from typing import TYPE_CHECKING, Any

from usif.codec import decode, encode
from usif.errors import (
    ChecksumError,
    DatasetError,
    FormatError,
    MissingDependencyError,
    UnsupportedVersionError,
    USIFError,
    ValidationError,
)
from usif.io import convert, read, read_all, write, write_all
from usif.model import DEFAULT_SCHEMA, Cell, PropertySpec, Schema, Structure
from usif.version import (
    DATASET_SCHEMA_VERSION,
    FORMAT_VERSION,
    RELEASE_DATE,
    RELEASE_ID,
    RELEASE_RECORD,
    __version__,
)

if TYPE_CHECKING:  # pragma: no cover
    from usif.dataset import Dataset, Q

__all__ = [
    "RELEASE_DATE",
    "RELEASE_ID",
    "RELEASE_RECORD",
    "DATASET_SCHEMA_VERSION",
    "DEFAULT_SCHEMA",
    "FORMAT_VERSION",
    "Cell",
    "ChecksumError",
    "Dataset",
    "DatasetError",
    "FormatError",
    "MissingDependencyError",
    "PropertySpec",
    "Q",
    "Schema",
    "Structure",
    "USIFError",
    "UnsupportedVersionError",
    "ValidationError",
    "__version__",
    "convert",
    "decode",
    "encode",
    "read",
    "read_all",
    "write",
    "write_all",
]


def __getattr__(name: str) -> Any:
    if name in ("Dataset", "Q"):
        from usif import dataset

        return getattr(dataset, name)
    raise AttributeError(f"module 'usif' has no attribute {name!r}")
