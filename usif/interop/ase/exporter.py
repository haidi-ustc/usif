"""USIF -> ASE exporter."""


class ASEExporter:
    """Export USIF structures to ASE Atoms objects."""

    @staticmethod
    def to_ase(usif_structure):
        from usif.interop.converter_core import StructureConverter as _CoreConverter

        return _CoreConverter.to_ase(usif_structure)
