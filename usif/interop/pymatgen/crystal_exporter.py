"""USIF crystal -> pymatgen exporter."""

from __future__ import annotations

import logging

from pymatgen.core import Element, Lattice
from pymatgen.core import Structure as PMGStructure

from usif.constants import StorageMode
from usif.structures.structure import USIFStructure
from usif.symmetry.equivalence import SymmetryOperations

logger = logging.getLogger(__name__)


class CrystalExporter:
    """Export crystal USIF structures to pymatgen ``Structure`` objects."""

    @staticmethod
    def to_pymatgen_structure(usif_structure: USIFStructure) -> PMGStructure:
        lattice = Lattice(usif_structure.lattice_matrix)
        species = []
        coords = []
        site_properties = {}

        if usif_structure.storage_mode == StorageMode.SYMMETRIC:
            try:
                from pymatgen.symmetry.groups import SpaceGroup

                symmetry_ops = SpaceGroup.from_int_number(
                    usif_structure.spacegroup
                ).symmetry_ops
            except Exception as e:
                logger.warning(
                    "Could not resolve space group %s; repeating representative sites: %s",
                    usif_structure.spacegroup,
                    e,
                )
                symmetry_ops = None

            expanded_sites = []
            for site in usif_structure.wyckoff_sites:
                element = Element.from_Z(site.atomic_number)
                if symmetry_ops is None:
                    site_coords = [site.coords] * site.multiplicity
                else:
                    site_coords = SymmetryOperations.expand_fractional_orbit(
                        site.coords, symmetry_ops, site.multiplicity
                    )
                for coord in site_coords:
                    expanded_sites.append((element, coord))

            expanded_sites.sort(key=lambda item: (item[0].Z, item[1]))
            for element, coord in expanded_sites:
                species.append(element)
                coords.append(coord)
        else:
            forces = []
            charges = []
            magmoms = []
            has_force = False
            has_charge = False
            has_magmom = False

            for site in usif_structure.atom_sites:
                element = Element.from_Z(site.atomic_number)
                species.append(element)
                coords.append(site.coords)

                site_force = site.properties.force
                site_charge = site.properties.charge
                site_magmom = site.properties.magmom
                forces.append(tuple(site_force) if site_force is not None else (0.0, 0.0, 0.0))
                charges.append(float(site_charge) if site_charge is not None else 0.0)
                magmoms.append(float(site_magmom) if site_magmom is not None else 0.0)
                has_force = has_force or site_force is not None
                has_charge = has_charge or site_charge is not None
                has_magmom = has_magmom or site_magmom is not None

            if has_force:
                site_properties["forces"] = forces
            if has_charge:
                site_properties["charges"] = charges
            if has_magmom:
                site_properties["magmoms"] = magmoms

        return PMGStructure(
            lattice,
            species,
            coords,
            coords_are_cartesian=False,
            site_properties=site_properties if site_properties else None,
        )
