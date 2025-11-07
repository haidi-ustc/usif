#!/usr/bin/env python3
"""
USIF Physical Units
Physical unit constants and utilities for materials science properties

This module provides standardized unit definitions for USIF properties.
Units are stored as strings for simplicity, but this module ensures consistency
and provides a central location for unit management.
"""

from typing import Dict, Set, Optional, Tuple


class Units:
    """
    Physical unit constants for materials science properties
    
    All units use standard SI-derived units commonly used in computational materials science.
    """
    
    # Energy units
    EV = "eV"  # Electron volt
    J = "J"  # Joule
    KJ_MOL = "kJ/mol"  # Kilojoule per mole
    KCAL_MOL = "kcal/mol"  # Kilocalorie per mole
    
    # Length units
    ANGSTROM = "Å"  # Angstrom
    NANOMETER = "nm"  # Nanometer
    METER = "m"  # Meter
    BOHR = "a₀"  # Bohr radius
    
    # Volume units
    ANGSTROM_CUBED = "Å³"  # Cubic Angstrom
    NANOMETER_CUBED = "nm³"  # Cubic nanometer
    
    # Force units
    EV_PER_ANGSTROM = "eV/Å"  # Electron volt per Angstrom
    NEWTON = "N"  # Newton
    
    # Pressure/Stress units
    GPA = "GPa"  # Gigapascal
    MPA = "MPa"  # Megapascal
    PA = "Pa"  # Pascal
    BAR = "bar"  # Bar
    ATM = "atm"  # Atmosphere
    KBAR = "kbar"  # Kilobar
    
    # Temperature units
    KELVIN = "K"  # Kelvin
    CELSIUS = "°C"  # Celsius
    FAHRENHEIT = "°F"  # Fahrenheit
    
    # Charge units
    ELEMENTARY_CHARGE = "e"  # Elementary charge
    COULOMB = "C"  # Coulomb
    
    # Magnetic moment units
    BOHR_MAGNETON = "μB"  # Bohr magneton
    J_T = "J/T"  # Joule per Tesla
    
    # Time units
    SECOND = "s"  # Second
    FEMTOSECOND = "fs"  # Femtosecond
    PICOSECOND = "ps"  # Picosecond
    
    # Velocity units
    ANGSTROM_PER_FS = "Å/fs"  # Angstrom per femtosecond
    M_PER_S = "m/s"  # Meter per second
    
    # Frequency units
    HERTZ = "Hz"  # Hertz
    THZ = "THz"  # Terahertz
    CM_INV = "cm⁻¹"  # Wavenumber (cm^-1)
    
    # Mass units
    AMU = "amu"  # Atomic mass unit
    KG = "kg"  # Kilogram
    G = "g"  # Gram
    
    # Density units
    G_PER_CM3 = "g/cm³"  # Grams per cubic centimeter
    KG_PER_M3 = "kg/m³"  # Kilograms per cubic meter
    
    # Unit categories for validation
    ENERGY_UNITS: Set[str] = {EV, J, KJ_MOL, KCAL_MOL}
    LENGTH_UNITS: Set[str] = {ANGSTROM, NANOMETER, METER, BOHR}
    VOLUME_UNITS: Set[str] = {ANGSTROM_CUBED, NANOMETER_CUBED}
    FORCE_UNITS: Set[str] = {EV_PER_ANGSTROM, NEWTON}
    PRESSURE_UNITS: Set[str] = {GPA, MPA, PA, BAR, ATM, KBAR}
    TEMPERATURE_UNITS: Set[str] = {KELVIN, CELSIUS, FAHRENHEIT}
    CHARGE_UNITS: Set[str] = {ELEMENTARY_CHARGE, COULOMB}
    MAGNETIC_MOMENT_UNITS: Set[str] = {BOHR_MAGNETON, J_T}
    TIME_UNITS: Set[str] = {SECOND, FEMTOSECOND, PICOSECOND}
    VELOCITY_UNITS: Set[str] = {ANGSTROM_PER_FS, M_PER_S}
    
    # Standard units used in USIF (defaults)
    STANDARD_ENERGY = EV
    STANDARD_LENGTH = ANGSTROM
    STANDARD_VOLUME = ANGSTROM_CUBED
    STANDARD_FORCE = EV_PER_ANGSTROM
    STANDARD_PRESSURE = GPA
    STANDARD_TEMPERATURE = KELVIN
    STANDARD_CHARGE = ELEMENTARY_CHARGE
    STANDARD_MAGNETIC_MOMENT = BOHR_MAGNETON
    STANDARD_TIME = FEMTOSECOND
    STANDARD_VELOCITY = ANGSTROM_PER_FS
    
    @classmethod
    def is_valid_unit(cls, unit: str) -> bool:
        """Check if a unit string is recognized"""
        all_units = (
            cls.ENERGY_UNITS | cls.LENGTH_UNITS | cls.VOLUME_UNITS |
            cls.FORCE_UNITS | cls.PRESSURE_UNITS | cls.TEMPERATURE_UNITS |
            cls.CHARGE_UNITS | cls.MAGNETIC_MOMENT_UNITS | cls.TIME_UNITS |
            cls.VELOCITY_UNITS
        )
        return unit in all_units
    
    @classmethod
    def get_unit_category(cls, unit: str) -> Optional[str]:
        """Get the category of a unit"""
        if unit in cls.ENERGY_UNITS:
            return "energy"
        elif unit in cls.LENGTH_UNITS:
            return "length"
        elif unit in cls.VOLUME_UNITS:
            return "volume"
        elif unit in cls.FORCE_UNITS:
            return "force"
        elif unit in cls.PRESSURE_UNITS:
            return "pressure"
        elif unit in cls.TEMPERATURE_UNITS:
            return "temperature"
        elif unit in cls.CHARGE_UNITS:
            return "charge"
        elif unit in cls.MAGNETIC_MOMENT_UNITS:
            return "magnetic_moment"
        elif unit in cls.TIME_UNITS:
            return "time"
        elif unit in cls.VELOCITY_UNITS:
            return "velocity"
        return None
    
    @classmethod
    def are_compatible(cls, unit1: str, unit2: str) -> bool:
        """Check if two units are compatible (same category)"""
        cat1 = cls.get_unit_category(unit1)
        cat2 = cls.get_unit_category(unit2)
        return cat1 is not None and cat1 == cat2


# Unit conversion factors (to standard USIF units)
# These can be used for future unit conversion functionality
class UnitConversions:
    """
    Unit conversion factors to standard USIF units
    
    All conversions are to the standard USIF unit for each category.
    """
    
    # Energy: eV (standard)
    EV_TO_EV = 1.0
    J_TO_EV = 6.241509074e18  # 1 J = 6.241509074e18 eV
    KJ_MOL_TO_EV = 0.01036427  # 1 kJ/mol ≈ 0.01036427 eV
    KCAL_MOL_TO_EV = 0.0433641  # 1 kcal/mol ≈ 0.0433641 eV
    
    # Length: Å (standard)
    ANGSTROM_TO_ANGSTROM = 1.0
    NANOMETER_TO_ANGSTROM = 10.0  # 1 nm = 10 Å
    METER_TO_ANGSTROM = 1e10  # 1 m = 1e10 Å
    BOHR_TO_ANGSTROM = 0.529177  # 1 a₀ ≈ 0.529177 Å
    
    # Volume: Å³ (standard)
    ANGSTROM_CUBED_TO_ANGSTROM_CUBED = 1.0
    NANOMETER_CUBED_TO_ANGSTROM_CUBED = 1000.0  # 1 nm³ = 1000 Å³
    
    # Force: eV/Å (standard)
    EV_PER_ANGSTROM_TO_EV_PER_ANGSTROM = 1.0
    NEWTON_TO_EV_PER_ANGSTROM = 6.241509074e18 / 1e10  # N to eV/Å
    
    # Pressure: GPa (standard)
    GPA_TO_GPA = 1.0
    MPA_TO_GPA = 0.001  # 1 MPa = 0.001 GPa
    PA_TO_GPA = 1e-9  # 1 Pa = 1e-9 GPa
    BAR_TO_GPA = 0.0001  # 1 bar = 0.0001 GPa
    ATM_TO_GPA = 0.000101325  # 1 atm ≈ 0.000101325 GPa
    KBAR_TO_GPA = 0.1  # 1 kbar = 0.1 GPa
    
    # Temperature: K (standard)
    KELVIN_TO_KELVIN = 1.0
    CELSIUS_TO_KELVIN = lambda c: c + 273.15  # °C to K (offset)
    FAHRENHEIT_TO_KELVIN = lambda f: (f - 32) * 5/9 + 273.15  # °F to K
    
    # Charge: e (standard)
    ELEMENTARY_CHARGE_TO_ELEMENTARY_CHARGE = 1.0
    COULOMB_TO_ELEMENTARY_CHARGE = 6.241509074e18  # 1 C = 6.241509074e18 e
    
    # Magnetic moment: μB (standard)
    BOHR_MAGNETON_TO_BOHR_MAGNETON = 1.0
    J_T_TO_BOHR_MAGNETON = 1.0 / 9.274009994e-24  # J/T to μB
    
    # Time: fs (standard)
    FEMTOSECOND_TO_FEMTOSECOND = 1.0
    SECOND_TO_FEMTOSECOND = 1e15  # 1 s = 1e15 fs
    PICOSECOND_TO_FEMTOSECOND = 1000.0  # 1 ps = 1000 fs
    
    # Velocity: Å/fs (standard)
    ANGSTROM_PER_FS_TO_ANGSTROM_PER_FS = 1.0
    M_PER_S_TO_ANGSTROM_PER_FS = 1e-5  # 1 m/s = 1e-5 Å/fs
    
    @classmethod
    def get_conversion_factor(cls, from_unit: str, to_unit: str) -> Optional[float]:
        """
        Get conversion factor from one unit to another
        
        Args:
            from_unit: Source unit
            to_unit: Target unit
            
        Returns:
            Conversion factor (multiply source value by this to get target value)
            Returns None if units are incompatible or conversion not supported
        """
        from_units = Units()
        to_units = Units()
        
        # Check if units are compatible
        if not from_units.are_compatible(from_unit, to_unit):
            return None
        
        # Get category
        category = from_units.get_unit_category(from_unit)
        if category is None:
            return None
        
        # For now, only support conversions to standard units
        # This can be extended later
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
        
        standard = standard_units.get(category)
        if standard is None:
            return None
        
        # If already in standard unit, return 1.0
        if from_unit == standard and to_unit == standard:
            return 1.0
        
        # For now, return None for non-standard conversions
        # This can be implemented later with a full conversion table
        return None

