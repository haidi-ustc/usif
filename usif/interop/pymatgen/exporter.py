"""USIF -> pymatgen exporter."""

import logging
from typing import Union

import numpy as np
from pymatgen.core import Element, Lattice
from pymatgen.core import Molecule as PMGMolecule
from pymatgen.core import Structure as PMGStructure

from usif.constants import StorageMode
from usif.structures.structure import USIFStructure
from usif.symmetry import POINT_GROUP_ALIASES, SymmetryOperations

logger = logging.getLogger(__name__)


class PymatgenExporter:
    """Export USIF structures to pymatgen Structure or Molecule objects."""

    @staticmethod
    def to_pymatgen(usif_structure: USIFStructure) -> Union[PMGStructure, PMGMolecule]:
        """Convert a USIFStructure to a pymatgen Structure or Molecule."""
        if usif_structure.is_molecular():
            return PymatgenExporter._to_molecule(usif_structure)
        return PymatgenExporter._to_crystal(usif_structure)

    @staticmethod
    def _to_molecule(usif_structure: USIFStructure) -> PMGMolecule:
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

    @staticmethod
    def _to_crystal(usif_structure: USIFStructure) -> PMGStructure:
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
