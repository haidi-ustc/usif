"""Materials Project data for USIF: download, load, and map to structures and datasets.

Run ``python -m scripts.materials_project --help`` from the repository root.
Needs ``pip install usif[mp]`` (mp-api, monty).
"""

from .archive import create_mp_data_archive, load_mp_data_from_archive, safe_extract
from .downloader import download_mp_data
from .loader import load_mp_group
from .mapper import NUMERIC_FIELDS, convert_mp_to_usif, structure_from_dict

__all__ = [
    "NUMERIC_FIELDS",
    "convert_mp_to_usif",
    "create_mp_data_archive",
    "download_mp_data",
    "load_mp_data_from_archive",
    "load_mp_group",
    "safe_extract",
    "structure_from_dict",
]
