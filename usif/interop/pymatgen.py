"""Pymatgen import/export adapters for USIF structures."""


class PymatgenImporter:
    """Import pymatgen Structure or Molecule objects into USIF."""

    @staticmethod
    def from_pymatgen(pmg_obj, **kwargs):
        from usif.converter import StructureConverter

        return StructureConverter.from_pymatgen(pmg_obj, **kwargs)


class PymatgenExporter:
    """Export USIF structures to pymatgen Structure or Molecule objects."""

    @staticmethod
    def to_pymatgen(usif_structure):
        from usif.converter import StructureConverter

        return StructureConverter.to_pymatgen(usif_structure)
