"""Application services for loading, saving, importing, exporting, and optimizing structures.

The core ``USIFStructure`` model intentionally contains no file I/O or external
conversion methods. Use these service functions at application boundaries.
"""

from .convert import (
    export_structure,
    import_matsimpy,
    import_pymatgen,
    import_structure,
    read_foreign_file,
)
from .io import load_structure, save_structure
from .json_io import (
    load_structure_json,
    save_structure_json,
    structure_from_json_dict,
    structure_to_json_dict,
)
from .optimizer import USIFOptimizer, optimize_structure

__all__ = [
    "USIFOptimizer",
    "export_structure",
    "import_matsimpy",
    "import_pymatgen",
    "import_structure",
    "load_structure",
    "load_structure_json",
    "optimize_structure",
    "read_foreign_file",
    "save_structure",
    "save_structure_json",
    "structure_from_json_dict",
    "structure_to_json_dict",
]
