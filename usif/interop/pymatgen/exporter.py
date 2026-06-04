"""USIF -> pymatgen exporter."""


class PymatgenExporter:
    """Export USIF structures to pymatgen Structure or Molecule objects."""

    @staticmethod
    def to_pymatgen(usif_structure):
        from usif.interop.converter_core import StructureConverter as _CoreConverter

        return _CoreConverter.to_pymatgen(usif_structure)
