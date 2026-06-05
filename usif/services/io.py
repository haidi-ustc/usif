"""Persistence services for USIF structures."""

import json
from pathlib import Path
from typing import Union

from usif.constants import CompressionType
from usif.exceptions import StorageError
from usif.structures import USIFStructure


def save_structure(
    structure: USIFStructure,
    filename: Union[str, Path],
    compression: CompressionType = CompressionType.GZIP,
) -> None:
    """Save a structure as USIF binary or MSON JSON based on file extension."""
    filename = Path(filename)

    if filename.suffix.lower() == ".usif":
        from usif.encoder import USIF

        encoder = USIF(compression=compression)
        encoder.save(structure, filename)
        return

    try:
        from monty.serialization import dumpfn

        dumpfn(structure, filename, indent=2)
    except IOError as e:
        raise StorageError(f"Failed to save structure to {filename}: {e}") from e


def load_structure(filename: Union[str, Path]) -> USIFStructure:
    """Load a structure from USIF binary or MSON JSON based on file extension."""
    filename = Path(filename)

    if filename.suffix.lower() == ".usif":
        try:
            with open(filename, "rb") as f:
                magic = f.read(7)
                if magic == b"USIFC\x00\x00":
                    raise StorageError(
                        f"File {filename} is a StructureContainer, not a USIF structure. "
                        f"Use StructureContainer() to open it."
                    )
        except (IOError, FileNotFoundError):
            pass

        from usif.encoder import USIF

        encoder = USIF()
        return encoder.load(filename)

    try:
        with open(filename, "r") as f:
            data = json.load(f)
        return USIFStructure.from_dict(data)
    except (IOError, FileNotFoundError) as e:
        raise StorageError(f"Failed to load structure from {filename}: {e}") from e
