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
