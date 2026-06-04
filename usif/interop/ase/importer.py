"""ASE -> USIF importer."""


class ASEImporter:
    """Import ASE Atoms objects into USIF."""

    @staticmethod
    def from_ase(ase_atoms, **kwargs):
        from usif.interop.converter_core import StructureConverter as _CoreConverter

        return _CoreConverter.from_ase(ase_atoms, **kwargs)
