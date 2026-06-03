"""ASE import/export adapters for USIF structures."""


class ASEImporter:
    """Import ASE Atoms objects into USIF."""

    @staticmethod
    def from_ase(ase_atoms, **kwargs):
        from usif.converter import StructureConverter

        return StructureConverter.from_ase(ase_atoms, **kwargs)


class ASEExporter:
    """Export USIF structures to ASE Atoms objects."""

    @staticmethod
    def to_ase(usif_structure):
        from usif.converter import StructureConverter

        return StructureConverter.to_ase(usif_structure)
