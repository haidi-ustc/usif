"""USIF molecule -> pymatgen exporter."""

from __future__ import annotations

import logging

from pymatgen.core import Element
from pymatgen.core import Molecule as PMGMolecule

from usif.constants import StorageMode
from usif.structures.structure import USIFStructure
from usif.symmetry.equivalence import POINT_GROUP_ALIASES, SymmetryOperations

logger = logging.getLogger(__name__)


class MoleculeExporter:
    """Export molecule USIF structures to pymatgen ``Molecule`` objects."""

    @staticmethod
    def to_pymatgen_molecule(usif_structure: USIFStructure) -> PMGMolecule:
        species = []
        coords = []
        site_properties = {}
        forces = []
        charges = []
        has_force = False
        has_charge = False

        if usif_structure.storage_mode == StorageMode.SYMMETRIC:
            point_group = usif_structure.point_group or "1"
            expanded_sites = []
            try:
                from pymatgen.symmetry.groups import PointGroup

                pg_symbol = POINT_GROUP_ALIASES.get(point_group, point_group)
                symmetry_ops = PointGroup(pg_symbol).symmetry_ops
            except Exception as e:
                logger.warning(
                    "Could not resolve point group %s; repeating representative sites: %s",
                    point_group,
                    e,
                )
                symmetry_ops = None

            for site in usif_structure.point_group_sites:
                element = Element.from_Z(site.atomic_number)
                if symmetry_ops is None:
                    site_coords = [site.coords] * site.multiplicity
                else:
                    site_coords = SymmetryOperations.expand_cartesian_orbit(
                        site.coords, symmetry_ops, site.multiplicity
                    )
                for coord in site_coords:
                    expanded_sites.append((element, coord))

            expanded_sites.sort(key=lambda item: (item[0].Z, item[1]))
            for element, coord in expanded_sites:
                species.append(element)
                coords.append(coord)
        else:
            for atom in usif_structure.atom_sites:
                element = Element.from_Z(atom.atomic_number)
                species.append(element)
                coords.append(atom.coords)

                atom_force = atom.properties.force
                atom_charge = atom.properties.charge
                forces.append(tuple(atom_force) if atom_force is not None else (0.0, 0.0, 0.0))
                charges.append(float(atom_charge) if atom_charge is not None else 0.0)
                has_force = has_force or atom_force is not None
                has_charge = has_charge or atom_charge is not None

        if has_force:
            site_properties["forces"] = forces
        if has_charge:
            site_properties["charges"] = charges

        return PMGMolecule(
            species,
            coords,
            site_properties=site_properties if site_properties else None,
        )
