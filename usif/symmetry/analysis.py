"""Thin wrappers around pymatgen symmetry analyzers."""

from typing import List, Tuple

from usif.structures.sites import WyckoffSite


def spacegroup_analyzer(structure, *, symprec):
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    return SpacegroupAnalyzer(structure, symprec=symprec)


def pointgroup_analyzer(molecule):
    from pymatgen.symmetry.analyzer import PointGroupAnalyzer

    return PointGroupAnalyzer(molecule)


def extract_wyckoff_sites(
    pmg_structure, *, symprec: float
) -> Tuple[int, List[WyckoffSite]]:
    """Extract spacegroup number and Wyckoff representative sites.

    This is the single source of truth for crystal symmetry reduction: it is
    used by both the pymatgen importer and the :class:`SymmetryReducer` so the
    Wyckoff extraction logic lives in exactly one place.

    Args:
        pmg_structure: A pymatgen ``Structure``.
        symprec: Symmetry precision (Angstrom) passed to ``SpacegroupAnalyzer``.

    Returns:
        Tuple ``(spacegroup_number, wyckoff_sites)`` where ``wyckoff_sites`` is a
        list of representative :class:`WyckoffSite` objects with multiplicities.
    """
    sga = spacegroup_analyzer(pmg_structure, symprec=symprec)
    spacegroup_number = sga.get_space_group_number()
    symmetrized = sga.get_symmetrized_structure()

    wyckoff_sites: List[WyckoffSite] = []
    for equiv_sites in symmetrized.equivalent_sites:
        rep = equiv_sites[0]
        wyckoff_sites.append(
            WyckoffSite(rep.specie.Z, len(equiv_sites), tuple(rep.frac_coords))
        )

    return spacegroup_number, wyckoff_sites



def extract_point_group_sites(pmg_molecule, *, tolerance: float):
    """Extract point group representatives for a pymatgen ``Molecule``."""
    from collections import defaultdict

    import numpy as np

    from usif.structures.sites import PointGroupSite

    pga = pointgroup_analyzer(pmg_molecule)
    point_group = pga.sch_symbol

    atom_groups = defaultdict(list)
    for i, site in enumerate(pmg_molecule):
        atom_groups[site.specie.Z].append((i, np.array(site.coords)))

    point_group_sites = []
    used = set()
    symmetry_operations = pga.get_symmetry_operations()

    for atomic_number, atoms in atom_groups.items():
        for idx, coords in atoms:
            if idx in used:
                continue

            multiplicity = 1
            used.add(idx)

            for other_idx, other_coords in atoms:
                if other_idx in used:
                    continue

                min_distance = float("inf")
                for sym_op in symmetry_operations:
                    transformed = sym_op.operate(coords)
                    distance = np.linalg.norm(transformed - other_coords)
                    min_distance = min(min_distance, distance)

                if min_distance < tolerance:
                    multiplicity += 1
                    used.add(other_idx)

            point_group_sites.append(
                PointGroupSite(atomic_number, multiplicity, tuple(coords))
            )

    return point_group, point_group_sites
