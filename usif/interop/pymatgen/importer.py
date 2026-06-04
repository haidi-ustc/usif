"""pymatgen -> USIF importer."""


class PymatgenImporter:
    """Import pymatgen Structure or Molecule objects into USIF."""

    @staticmethod
    def from_pymatgen(pmg_obj, **kwargs):
        from usif.interop.converter_core import StructureConverter as _CoreConverter

        return _CoreConverter.from_pymatgen(pmg_obj, **kwargs)
