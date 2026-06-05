"""USIF -> pymatgen exporter facade."""

from __future__ import annotations

from typing import Union

from pymatgen.core import Molecule as PMGMolecule
from pymatgen.core import Structure as PMGStructure

from usif.interop.pymatgen.crystal_exporter import CrystalExporter
from usif.interop.pymatgen.molecule_exporter import MoleculeExporter
from usif.structures.structure import USIFStructure


class PymatgenExporter:
    """Dispatch USIF exports to focused pymatgen exporters."""

    @staticmethod
    def to_pymatgen(usif_structure: USIFStructure) -> Union[PMGStructure, PMGMolecule]:
        """Convert a USIFStructure to a pymatgen Structure or Molecule."""
        if usif_structure.is_molecular():
            return MoleculeExporter.to_pymatgen_molecule(usif_structure)
        return CrystalExporter.to_pymatgen_structure(usif_structure)
