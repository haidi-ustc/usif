"""Thin wrappers around pymatgen symmetry analyzers."""


def spacegroup_analyzer(structure, *, symprec):
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    return SpacegroupAnalyzer(structure, symprec=symprec)


def pointgroup_analyzer(molecule):
    from pymatgen.symmetry.analyzer import PointGroupAnalyzer

    return PointGroupAnalyzer(molecule)
