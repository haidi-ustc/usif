"""Periodic-table data used by the core (symbols and Pauling electronegativity).

Electronegativities follow the values pymatgen uses, so :func:`usif.formula.reduced_formula`
orders elements exactly as USIF 0.7.x did. ``None`` marks elements without a value.
"""

from typing import Dict, Optional, Tuple

#: (atomic_number, symbol, pauling_electronegativity)
ELEMENTS: Tuple[Tuple[int, str, Optional[float]], ...] = (
    (1, "H", 2.2),
    (2, "He", None),
    (3, "Li", 0.98),
    (4, "Be", 1.57),
    (5, "B", 2.04),
    (6, "C", 2.55),
    (7, "N", 3.04),
    (8, "O", 3.44),
    (9, "F", 3.98),
    (10, "Ne", None),
    (11, "Na", 0.93),
    (12, "Mg", 1.31),
    (13, "Al", 1.61),
    (14, "Si", 1.9),
    (15, "P", 2.19),
    (16, "S", 2.58),
    (17, "Cl", 3.16),
    (18, "Ar", None),
    (19, "K", 0.82),
    (20, "Ca", 1.0),
    (21, "Sc", 1.36),
    (22, "Ti", 1.54),
    (23, "V", 1.63),
    (24, "Cr", 1.66),
    (25, "Mn", 1.55),
    (26, "Fe", 1.83),
    (27, "Co", 1.88),
    (28, "Ni", 1.91),
    (29, "Cu", 1.9),
    (30, "Zn", 1.65),
    (31, "Ga", 1.81),
    (32, "Ge", 2.01),
    (33, "As", 2.18),
    (34, "Se", 2.55),
    (35, "Br", 2.96),
    (36, "Kr", 3.0),
    (37, "Rb", 0.82),
    (38, "Sr", 0.95),
    (39, "Y", 1.22),
    (40, "Zr", 1.33),
    (41, "Nb", 1.6),
    (42, "Mo", 2.16),
    (43, "Tc", 1.9),
    (44, "Ru", 2.2),
    (45, "Rh", 2.28),
    (46, "Pd", 2.2),
    (47, "Ag", 1.93),
    (48, "Cd", 1.69),
    (49, "In", 1.78),
    (50, "Sn", 1.96),
    (51, "Sb", 2.05),
    (52, "Te", 2.1),
    (53, "I", 2.66),
    (54, "Xe", 2.6),
    (55, "Cs", 0.79),
    (56, "Ba", 0.89),
    (57, "La", 1.1),
    (58, "Ce", 1.12),
    (59, "Pr", 1.13),
    (60, "Nd", 1.14),
    (61, "Pm", 1.13),
    (62, "Sm", 1.17),
    (63, "Eu", 1.2),
    (64, "Gd", 1.2),
    (65, "Tb", 1.1),
    (66, "Dy", 1.22),
    (67, "Ho", 1.23),
    (68, "Er", 1.24),
    (69, "Tm", 1.25),
    (70, "Yb", 1.1),
    (71, "Lu", 1.27),
    (72, "Hf", 1.3),
    (73, "Ta", 1.5),
    (74, "W", 2.36),
    (75, "Re", 1.9),
    (76, "Os", 2.2),
    (77, "Ir", 2.2),
    (78, "Pt", 2.28),
    (79, "Au", 2.54),
    (80, "Hg", 2.0),
    (81, "Tl", 1.62),
    (82, "Pb", 2.33),
    (83, "Bi", 2.02),
    (84, "Po", 2.0),
    (85, "At", 2.2),
    (86, "Rn", 2.2),
    (87, "Fr", 0.7),
    (88, "Ra", 0.9),
    (89, "Ac", 1.1),
    (90, "Th", 1.3),
    (91, "Pa", 1.5),
    (92, "U", 1.38),
    (93, "Np", 1.36),
    (94, "Pu", 1.28),
    (95, "Am", 1.3),
    (96, "Cm", 1.3),
    (97, "Bk", 1.3),
    (98, "Cf", 1.3),
    (99, "Es", 1.3),
    (100, "Fm", 1.3),
    (101, "Md", 1.3),
    (102, "No", 1.3),
    (103, "Lr", 1.3),
    (104, "Rf", None),
    (105, "Db", None),
    (106, "Sg", None),
    (107, "Bh", None),
    (108, "Hs", None),
    (109, "Mt", None),
    (110, "Ds", None),
    (111, "Rg", None),
    (112, "Cn", None),
    (113, "Nh", None),
    (114, "Fl", None),
    (115, "Mc", None),
    (116, "Lv", None),
    (117, "Ts", None),
    (118, "Og", None),
)

SYMBOL_BY_Z: Dict[int, str] = {z: symbol for z, symbol, _ in ELEMENTS}
Z_BY_SYMBOL: Dict[str, int] = {symbol: z for z, symbol, _ in ELEMENTS}
ELECTRONEGATIVITY: Dict[str, Optional[float]] = {symbol: x for _, symbol, x in ELEMENTS}


def atomic_number(symbol: str) -> int:
    """Return the atomic number for an element symbol (e.g. ``"Fe"`` -> 26)."""
    try:
        return Z_BY_SYMBOL[symbol]
    except KeyError:
        raise ValueError(f"Unknown element symbol {symbol!r}") from None


def element_symbol(z: int) -> str:
    """Return the element symbol for an atomic number (e.g. ``26`` -> ``"Fe"``)."""
    try:
        return SYMBOL_BY_Z[int(z)]
    except KeyError:
        raise ValueError(f"Unknown atomic number {z!r}") from None
