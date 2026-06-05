"""USIF -> ASE exporter."""

import numpy as np

from usif.constants import StorageMode
from usif.structures.structure import USIFStructure

try:
    from ase import Atoms as ASEAtoms  # noqa: F401
except ImportError:  # pragma: no cover - exercised only without ASE installed
    ASEAtoms = None


class ASEExporter:
    """Export USIF structures to ASE Atoms objects."""

    @staticmethod
    def to_ase(usif_structure: USIFStructure):
        """Convert a USIFStructure to an ASE Atoms object."""
        if ASEAtoms is None:
            raise ImportError("ASE is not installed. Install it with: pip install ase")

        from pymatgen.io.ase import AseAtomsAdaptor
        from usif.interop.pymatgen.exporter import PymatgenExporter

        pmg_obj = PymatgenExporter.to_pymatgen(usif_structure)
        ase_atoms = AseAtomsAdaptor().get_atoms(pmg_obj)

        if usif_structure.structure_properties.energy is not None:
            ase_atoms.calc = None
            ase_atoms.info["energy"] = usif_structure.structure_properties.energy

        if usif_structure.storage_mode == StorageMode.FULL_ATOMIC:
            forces = [
                atom.properties.force if atom.properties.force is not None else [0.0, 0.0, 0.0]
                for atom in usif_structure.atom_sites
            ]
            if forces and any(any(f != 0.0 for f in force) for force in forces):
                ase_atoms.set_array("forces", np.array(forces))

            charges = [
                atom.properties.charge if atom.properties.charge is not None else 0.0
                for atom in usif_structure.atom_sites
            ]
            if charges and any(c != 0.0 for c in charges):
                ase_atoms.set_charges(charges)

            magmoms = [
                atom.properties.magmom if atom.properties.magmom is not None else 0.0
                for atom in usif_structure.atom_sites
            ]
            if magmoms and any(m != 0.0 for m in magmoms):
                ase_atoms.set_initial_magnetic_moments(magmoms)

        return ase_atoms
