"""Persistence services for USIF structures."""

from pathlib import Path
from typing import Union

from usif.constants import CompressionType
from usif.exceptions import StorageError
from usif.structures import USIFStructure

_JSON_SUFFIXES = {".json", ".usif.json"}


def _is_json_path(filename: Path) -> bool:
    """Return True when a path should use the official USIF JSON codec."""
    suffix = filename.suffix.lower()
    return suffix in _JSON_SUFFIXES or filename.name.lower().endswith(".usif.json")


def save_structure(
    structure: USIFStructure,
    filename: Union[str, Path],
    compression: CompressionType = CompressionType.GZIP,
) -> None:
    """Save a structure as ``.usif`` binary or official USIF JSON.

    Supported extensions:
        - ``.usif``: compact binary USIF record.
        - ``.json`` / ``.usif.json``: human-readable JSON structure document.
    """
    filename = Path(filename)

    if filename.suffix.lower() == ".usif":
        from usif.encoder import USIF

        encoder = USIF(compression=compression)
        encoder.save(structure, filename)
        return

    if _is_json_path(filename):
        from usif.services.json_io import save_structure_json

        save_structure_json(structure, filename)
        return

    raise StorageError(
        f"Unsupported structure file extension for {filename}. "
        "Use .usif, .json, or .usif.json."
    )


def load_structure(filename: Union[str, Path]) -> USIFStructure:
    """Load a structure from ``.usif`` binary or official USIF JSON."""
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
        except FileNotFoundError as e:
            raise StorageError(f"Failed to load structure from {filename}: {e}") from e
        except IOError:
            pass

        from usif.encoder import USIF

        encoder = USIF()
        return encoder.load(filename)

    if _is_json_path(filename):
        from usif.services.json_io import load_structure_json

        return load_structure_json(filename)

    raise StorageError(
        f"Unsupported structure file extension for {filename}. "
        "Use .usif, .json, or .usif.json."
    )
