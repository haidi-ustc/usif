#!/usr/bin/env python3
"""
USIF physical units and unit normalization helpers.

USIF stores values in canonical project units but does not perform automatic
unit conversion in property setters.  Unit strings are normalized so users can
write convenient Unicode or ASCII aliases such as ``Å²``, ``Å^2``, ``Ang^2``
or ``angstrom^2`` and get the same canonical representation.
"""

from __future__ import annotations

import re
from typing import Optional, Set

_SUPERSCRIPT_TRANSLATION = str.maketrans(
    {
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
        "⁺": "+",
        "⁻": "-",
    }
)
_SUBSCRIPT_TRANSLATION = str.maketrans(
    {
        "₀": "0",
        "₁": "1",
        "₂": "2",
        "₃": "3",
        "₄": "4",
        "₅": "5",
        "₆": "6",
        "₇": "7",
        "₈": "8",
        "₉": "9",
        "₊": "+",
        "₋": "-",
    }
)


def _replace_superscript_runs(text: str) -> str:
    """Convert Unicode superscript runs to caret exponents."""

    chars = set("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    result: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char not in chars:
            result.append(char)
            index += 1
            continue
        start = index
        while index < len(text) and text[index] in chars:
            index += 1
        exponent = text[start:index].translate(_SUPERSCRIPT_TRANSLATION)
        result.append("^" + exponent)
    return "".join(result)


class Units:
    """Physical unit constants and normalization helpers for USIF."""

    # Energy units
    EV = "eV"
    J = "J"
    KJ_MOL = "kJ/mol"
    KCAL_MOL = "kcal/mol"

    # Length units
    ANGSTROM = "Å"
    NANOMETER = "nm"
    METER = "m"
    BOHR = "a0"

    # Volume units
    ANGSTROM_CUBED = "Å^3"
    NANOMETER_CUBED = "nm^3"

    # Common custom tensor units
    ANGSTROM_SQUARED = "Å^2"

    # Force units
    EV_PER_ANGSTROM = "eV/Å"
    NEWTON = "N"

    # Pressure/Stress units
    GPA = "GPa"
    MPA = "MPa"
    PA = "Pa"
    BAR = "bar"
    ATM = "atm"
    KBAR = "kbar"

    # Temperature units
    KELVIN = "K"
    CELSIUS = "°C"
    FAHRENHEIT = "°F"

    # Charge units
    ELEMENTARY_CHARGE = "e"
    COULOMB = "C"

    # Magnetic moment units
    BOHR_MAGNETON = "μB"
    J_T = "J/T"

    # Time units
    SECOND = "s"
    FEMTOSECOND = "fs"
    PICOSECOND = "ps"

    # Velocity units
    ANGSTROM_PER_FS = "Å/fs"
    M_PER_S = "m/s"

    # Frequency units
    HERTZ = "Hz"
    THZ = "THz"
    CM_INV = "cm^-1"

    # Mass units
    AMU = "amu"
    KG = "kg"
    G = "g"

    # Density units
    G_PER_CM3 = "g/cm^3"
    KG_PER_M3 = "kg/m^3"

    ENERGY_UNITS: Set[str] = {EV, J, KJ_MOL, KCAL_MOL}
    LENGTH_UNITS: Set[str] = {ANGSTROM, NANOMETER, METER, BOHR}
    VOLUME_UNITS: Set[str] = {ANGSTROM_CUBED, NANOMETER_CUBED}
    AREA_UNITS: Set[str] = {ANGSTROM_SQUARED, "nm^2", "m^2"}
    FORCE_UNITS: Set[str] = {EV_PER_ANGSTROM, NEWTON}
    PRESSURE_UNITS: Set[str] = {GPA, MPA, PA, BAR, ATM, KBAR}
    TEMPERATURE_UNITS: Set[str] = {KELVIN, CELSIUS, FAHRENHEIT}
    CHARGE_UNITS: Set[str] = {ELEMENTARY_CHARGE, COULOMB}
    MAGNETIC_MOMENT_UNITS: Set[str] = {BOHR_MAGNETON, J_T}
    TIME_UNITS: Set[str] = {SECOND, FEMTOSECOND, PICOSECOND}
    VELOCITY_UNITS: Set[str] = {ANGSTROM_PER_FS, M_PER_S}
    FREQUENCY_UNITS: Set[str] = {HERTZ, THZ, CM_INV}
    MASS_UNITS: Set[str] = {AMU, KG, G}
    DENSITY_UNITS: Set[str] = {G_PER_CM3, KG_PER_M3}

    STANDARD_ENERGY = EV
    STANDARD_LENGTH = ANGSTROM
    STANDARD_AREA = ANGSTROM_SQUARED
    STANDARD_VOLUME = ANGSTROM_CUBED
    STANDARD_FORCE = EV_PER_ANGSTROM
    STANDARD_PRESSURE = GPA
    STANDARD_TEMPERATURE = KELVIN
    STANDARD_CHARGE = ELEMENTARY_CHARGE
    STANDARD_MAGNETIC_MOMENT = BOHR_MAGNETON
    STANDARD_TIME = FEMTOSECOND
    STANDARD_VELOCITY = ANGSTROM_PER_FS

    _ANGSTROM_TOKEN_RE = re.compile(r"(?i)(?<![A-Za-z])(?:angstroms?|ang)(?![A-Za-z])")

    @classmethod
    def normalize_unit(cls, unit: Optional[str]) -> Optional[str]:
        """Return the canonical USIF spelling for a unit string.

        The normalizer intentionally accepts both Unicode and ASCII spellings.
        Examples include ``Å²``/``Å^2``/``Ang^2``/``angstrom^2`` -> ``Å^2``
        and ``eV/Ang``/``eV/Å`` -> ``eV/Å``.  The function normalizes spelling
        only; it does not convert numerical values.
        """

        if unit is None:
            return None
        if not isinstance(unit, str):
            raise TypeError(f"unit must be a string or None, got {type(unit).__name__}")
        text = unit.strip()
        if not text:
            return ""
        text = text.replace("Å", "Å")
        text = text.translate(_SUBSCRIPT_TRANSLATION)
        text = _replace_superscript_runs(text)
        text = text.replace(" ** ", "^").replace("**", "^")
        text = re.sub(r"\s*\^\s*", "^", text)
        text = re.sub(r"\s*/\s*", "/", text)
        text = re.sub(r"\s+", " ", text)
        text = cls._ANGSTROM_TOKEN_RE.sub("Å", text)
        text = re.sub(r"(?i)micro", "μ", text)
        text = text.replace("uB", "μB").replace("mu_B", "μB").replace("muB", "μB")
        text = text.replace("a₀", "a0")
        text = text.replace("Ang", "Å")
        return text

    @classmethod
    def canonicalize_units_map(cls, units: dict[str, str]) -> dict[str, str]:
        """Normalize every unit string in a property-unit mapping."""

        return {str(key): cls.normalize_unit(value) or "" for key, value in units.items()}

    @classmethod
    def _normalized_set(cls, units: Set[str]) -> Set[str]:
        return {cls.normalize_unit(unit) or "" for unit in units}

    @classmethod
    def all_units(cls) -> Set[str]:
        """Return all recognized units using canonical spellings."""

        all_units = (
            cls.ENERGY_UNITS
            | cls.LENGTH_UNITS
            | cls.AREA_UNITS
            | cls.VOLUME_UNITS
            | cls.FORCE_UNITS
            | cls.PRESSURE_UNITS
            | cls.TEMPERATURE_UNITS
            | cls.CHARGE_UNITS
            | cls.MAGNETIC_MOMENT_UNITS
            | cls.TIME_UNITS
            | cls.VELOCITY_UNITS
            | cls.FREQUENCY_UNITS
            | cls.MASS_UNITS
            | cls.DENSITY_UNITS
        )
        return cls._normalized_set(all_units)

    @classmethod
    def is_valid_unit(cls, unit: str) -> bool:
        """Check if a unit string is recognized after alias normalization."""

        return (cls.normalize_unit(unit) or "") in cls.all_units()

    @classmethod
    def get_unit_category(cls, unit: str) -> Optional[str]:
        """Return the physical category of a recognized unit."""

        normalized = cls.normalize_unit(unit) or ""
        categories = {
            "energy": cls.ENERGY_UNITS,
            "length": cls.LENGTH_UNITS,
            "area": cls.AREA_UNITS,
            "volume": cls.VOLUME_UNITS,
            "force": cls.FORCE_UNITS,
            "pressure": cls.PRESSURE_UNITS,
            "temperature": cls.TEMPERATURE_UNITS,
            "charge": cls.CHARGE_UNITS,
            "magnetic_moment": cls.MAGNETIC_MOMENT_UNITS,
            "time": cls.TIME_UNITS,
            "velocity": cls.VELOCITY_UNITS,
            "frequency": cls.FREQUENCY_UNITS,
            "mass": cls.MASS_UNITS,
            "density": cls.DENSITY_UNITS,
        }
        for category, units in categories.items():
            if normalized in cls._normalized_set(units):
                return category
        return None

    @classmethod
    def are_compatible(cls, unit1: str, unit2: str) -> bool:
        """Return True when two unit strings normalize into the same category."""

        cat1 = cls.get_unit_category(unit1)
        cat2 = cls.get_unit_category(unit2)
        return cat1 is not None and cat1 == cat2


class UnitConversions:
    """Conversion factors to standard USIF units.

    Property setters in 6.6 store unit metadata but do not automatically convert
    numerical values.  These constants are retained as low-level utilities.
    """

    EV_TO_EV = 1.0
    J_TO_EV = 6.241509074e18
    KJ_MOL_TO_EV = 0.01036427
    KCAL_MOL_TO_EV = 0.0433641

    ANGSTROM_TO_ANGSTROM = 1.0
    NANOMETER_TO_ANGSTROM = 10.0
    METER_TO_ANGSTROM = 1e10
    BOHR_TO_ANGSTROM = 0.529177

    ANGSTROM_CUBED_TO_ANGSTROM_CUBED = 1.0
    NANOMETER_CUBED_TO_ANGSTROM_CUBED = 1000.0

    EV_PER_ANGSTROM_TO_EV_PER_ANGSTROM = 1.0
    NEWTON_TO_EV_PER_ANGSTROM = 6.241509074e18 / 1e10

    GPA_TO_GPA = 1.0
    MPA_TO_GPA = 0.001
    PA_TO_GPA = 1e-9
    BAR_TO_GPA = 0.0001
    ATM_TO_GPA = 0.000101325
    KBAR_TO_GPA = 0.1

    KELVIN_TO_KELVIN = 1.0
    CELSIUS_TO_KELVIN = staticmethod(lambda c: c + 273.15)
    FAHRENHEIT_TO_KELVIN = staticmethod(lambda f: (f - 32) * 5 / 9 + 273.15)

    ELEMENTARY_CHARGE_TO_ELEMENTARY_CHARGE = 1.0
    COULOMB_TO_ELEMENTARY_CHARGE = 6.241509074e18

    BOHR_MAGNETON_TO_BOHR_MAGNETON = 1.0
    J_T_TO_BOHR_MAGNETON = 1.0 / 9.274009994e-24

    FEMTOSECOND_TO_FEMTOSECOND = 1.0
    SECOND_TO_FEMTOSECOND = 1e15
    PICOSECOND_TO_FEMTOSECOND = 1000.0

    ANGSTROM_PER_FS_TO_ANGSTROM_PER_FS = 1.0
    M_PER_S_TO_ANGSTROM_PER_FS = 1e-5

    @classmethod
    def get_conversion_factor(cls, from_unit: str, to_unit: str) -> Optional[float]:
        """Return a factor for supported conversions to the standard unit."""

        from_unit = Units.normalize_unit(from_unit) or ""
        to_unit = Units.normalize_unit(to_unit) or ""
        if not Units.are_compatible(from_unit, to_unit):
            return None

        category = Units.get_unit_category(from_unit)
        standard_units = {
            "energy": Units.STANDARD_ENERGY,
            "length": Units.STANDARD_LENGTH,
            "volume": Units.STANDARD_VOLUME,
            "force": Units.STANDARD_FORCE,
            "pressure": Units.STANDARD_PRESSURE,
            "temperature": Units.STANDARD_TEMPERATURE,
            "charge": Units.STANDARD_CHARGE,
            "magnetic_moment": Units.STANDARD_MAGNETIC_MOMENT,
            "time": Units.STANDARD_TIME,
            "velocity": Units.STANDARD_VELOCITY,
        }
        standard = standard_units.get(category or "")
        if standard is None:
            return None
        if from_unit == standard and to_unit == standard:
            return 1.0
        return None
