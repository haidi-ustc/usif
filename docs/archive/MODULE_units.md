# Module: units.py

## Overview

The `units.py` module provides standardized physical unit definitions and unit conversion utilities for materials science properties. It ensures consistency in unit usage across the USIF system and provides a foundation for future unit conversion functionality. Units are stored as strings for simplicity, but the module provides validation and compatibility checking.

**Purpose**: Centralize unit definitions, provide unit validation, and establish foundation for unit conversion system.

**Role in Architecture**: Foundation layer - provides unit constants used by property system for type-safe property definitions with units.

## Architecture

The module consists of two main classes:

1. **Units**: Static class containing unit constants and validation methods
2. **UnitConversions**: Static class containing conversion factors (foundation for future conversion)

Both classes use class methods and class attributes, following a constants-only pattern with utility methods.

## Key Components

### Units Class

A static class providing physical unit constants organized by category (energy, length, volume, force, pressure, temperature, charge, magnetic moment, time, velocity).

#### Unit Constants

**Energy Units**:
- `EV = "eV"`: Electron volt (standard USIF energy unit)
- `J = "J"`: Joule
- `KJ_MOL = "kJ/mol"`: Kilojoule per mole
- `KCAL_MOL = "kcal/mol"`: Kilocalorie per mole

**Length Units**:
- `ANGSTROM = "Å"`: Angstrom (standard USIF length unit)
- `NANOMETER = "nm"`: Nanometer
- `METER = "m"`: Meter
- `BOHR = "a₀"`: Bohr radius

**Volume Units**:
- `ANGSTROM_CUBED = "Å³"`: Cubic Angstrom (standard USIF volume unit)
- `NANOMETER_CUBED = "nm³"`: Cubic nanometer

**Force Units**:
- `EV_PER_ANGSTROM = "eV/Å"`: Electron volt per Angstrom (standard USIF force unit)
- `NEWTON = "N"`: Newton

**Pressure/Stress Units**:
- `GPA = "GPa"`: Gigapascal (standard USIF pressure unit)
- `MPA = "MPa"`: Megapascal
- `PA = "Pa"`: Pascal
- `BAR = "bar"`: Bar
- `ATM = "atm"`: Atmosphere
- `KBAR = "kbar"`: Kilobar

**Temperature Units**:
- `KELVIN = "K"`: Kelvin (standard USIF temperature unit)
- `CELSIUS = "°C"`: Celsius
- `FAHRENHEIT = "°F"`: Fahrenheit

**Charge Units**:
- `ELEMENTARY_CHARGE = "e"`: Elementary charge (standard USIF charge unit)
- `COULOMB = "C"`: Coulomb

**Magnetic Moment Units**:
- `BOHR_MAGNETON = "μB"`: Bohr magneton (standard USIF magnetic moment unit)
- `J_T = "J/T"`: Joule per Tesla

**Time Units**:
- `SECOND = "s"`: Second
- `FEMTOSECOND = "fs"`: Femtosecond (standard USIF time unit)
- `PICOSECOND = "ps"`: Picosecond

**Velocity Units**:
- `ANGSTROM_PER_FS = "Å/fs"`: Angstrom per femtosecond (standard USIF velocity unit)
- `M_PER_S = "m/s"`: Meter per second

#### Unit Categories

Sets of units grouped by physical category for validation:
- `ENERGY_UNITS`: Set of all energy unit strings
- `LENGTH_UNITS`: Set of all length unit strings
- `VOLUME_UNITS`: Set of all volume unit strings
- `FORCE_UNITS`: Set of all force unit strings
- `PRESSURE_UNITS`: Set of all pressure unit strings
- `TEMPERATURE_UNITS`: Set of all temperature unit strings
- `CHARGE_UNITS`: Set of all charge unit strings
- `MAGNETIC_MOMENT_UNITS`: Set of all magnetic moment unit strings
- `TIME_UNITS`: Set of all time unit strings
- `VELOCITY_UNITS`: Set of all velocity unit strings

#### Standard Units

Default units used in USIF for each category:
- `STANDARD_ENERGY = EV`
- `STANDARD_LENGTH = ANGSTROM`
- `STANDARD_VOLUME = ANGSTROM_CUBED`
- `STANDARD_FORCE = EV_PER_ANGSTROM`
- `STANDARD_PRESSURE = GPA`
- `STANDARD_TEMPERATURE = KELVIN`
- `STANDARD_CHARGE = ELEMENTARY_CHARGE`
- `STANDARD_MAGNETIC_MOMENT = BOHR_MAGNETON`
- `STANDARD_TIME = FEMTOSECOND`
- `STANDARD_VELOCITY = ANGSTROM_PER_FS`

#### Class Methods

**is_valid_unit(unit: str) -> bool**:
- Checks if a unit string is recognized by USIF
- Returns True if unit exists in any category, False otherwise

**get_unit_category(unit: str) -> Optional[str]**:
- Returns the physical category of a unit (e.g., "energy", "length")
- Returns None if unit is not recognized
- Used for compatibility checking

**are_compatible(unit1: str, unit2: str) -> bool**:
- Checks if two units belong to the same category (can be converted)
- Returns True if units are compatible, False otherwise

**Usage Example**:
```python
from usif import Units, PropertyDefinition

# Use unit constants
prop_def = PropertyDefinition(
    name="energy",
    data_type=float,
    units=Units.EV
)

# Validate units
assert Units.is_valid_unit("eV")  # True
assert Units.is_valid_unit("invalid")  # False

# Check compatibility
assert Units.are_compatible("eV", "J")  # True (both energy)
assert Units.are_compatible("eV", "Å")  # False (different categories)

# Get category
category = Units.get_unit_category("GPa")  # "pressure"
```

### UnitConversions Class

A static class providing conversion factors to standard USIF units. Currently provides conversion factors but not full conversion functionality (foundation for future implementation).

#### Conversion Factors

All conversions are to standard USIF units:

**Energy Conversions** (to eV):
- `EV_TO_EV = 1.0`
- `J_TO_EV = 6.241509074e18`
- `KJ_MOL_TO_EV = 0.01036427`
- `KCAL_MOL_TO_EV = 0.0433641`

**Length Conversions** (to Å):
- `ANGSTROM_TO_ANGSTROM = 1.0`
- `NANOMETER_TO_ANGSTROM = 10.0`
- `METER_TO_ANGSTROM = 1e10`
- `BOHR_TO_ANGSTROM = 0.529177`

**Volume Conversions** (to Å³):
- `ANGSTROM_CUBED_TO_ANGSTROM_CUBED = 1.0`
- `NANOMETER_CUBED_TO_ANGSTROM_CUBED = 1000.0`

**Force Conversions** (to eV/Å):
- `EV_PER_ANGSTROM_TO_EV_PER_ANGSTROM = 1.0`
- `NEWTON_TO_EV_PER_ANGSTROM = 6.241509074e18 / 1e10`

**Pressure Conversions** (to GPa):
- `GPA_TO_GPA = 1.0`
- `MPA_TO_GPA = 0.001`
- `PA_TO_GPA = 1e-9`
- `BAR_TO_GPA = 0.0001`
- `ATM_TO_GPA = 0.000101325`
- `KBAR_TO_GPA = 0.1`

**Temperature Conversions** (to K):
- `KELVIN_TO_KELVIN = 1.0`
- `CELSIUS_TO_KELVIN`: Lambda function `lambda c: c + 273.15`
- `FAHRENHEIT_TO_KELVIN`: Lambda function `lambda f: (f - 32) * 5/9 + 273.15`

**Charge Conversions** (to e):
- `ELEMENTARY_CHARGE_TO_ELEMENTARY_CHARGE = 1.0`
- `COULOMB_TO_ELEMENTARY_CHARGE = 6.241509074e18`

**Magnetic Moment Conversions** (to μB):
- `BOHR_MAGNETON_TO_BOHR_MAGNETON = 1.0`
- `J_T_TO_BOHR_MAGNETON = 1.0 / 9.274009994e-24`

**Time Conversions** (to fs):
- `FEMTOSECOND_TO_FEMTOSECOND = 1.0`
- `SECOND_TO_FEMTOSECOND = 1e15`
- `PICOSECOND_TO_FEMTOSECOND = 1000.0`

**Velocity Conversions** (to Å/fs):
- `ANGSTROM_PER_FS_TO_ANGSTROM_PER_FS = 1.0`
- `M_PER_S_TO_ANGSTROM_PER_FS = 1e-5`

#### Class Methods

**get_conversion_factor(from_unit: str, to_unit: str) -> Optional[float]**:
- Gets conversion factor between two units
- Currently only supports conversions to standard USIF units
- Returns None if units are incompatible or conversion not supported
- Foundation for future full conversion implementation

**Usage Example**:
```python
from usif import UnitConversions, Units

# Get conversion factor (currently limited)
factor = UnitConversions.get_conversion_factor("J", Units.STANDARD_ENERGY)
# Returns conversion factor or None
```

## Dependencies

**Internal Dependencies**: None - foundational module.

**External Dependencies**: None - uses only Python standard library (`typing`).

**Used By**:
- `properties/registry.py`: Uses Units constants for built-in property definitions
- `properties/definitions.py`: PropertyDefinition stores unit strings
- Future: Unit conversion functionality

## Data Structures

- **Sets**: Unit category sets (ENERGY_UNITS, LENGTH_UNITS, etc.)
- **Strings**: Unit constant strings
- **Floats**: Conversion factor constants
- **Lambda functions**: Temperature conversion functions (offset-based)

## Usage Patterns

### Standard Unit Usage

```python
from usif import Units, PropertyDefinition

# Always use Units constants for consistency
prop_def = PropertyDefinition(
    name="energy",
    data_type=float,
    units=Units.EV  # Use constant, not string literal
)
```

### Unit Validation

```python
from usif import Units

# Validate user-provided units
user_unit = input("Enter unit: ")
if Units.is_valid_unit(user_unit):
    print(f"Valid unit: {user_unit}")
    category = Units.get_unit_category(user_unit)
    print(f"Category: {category}")
else:
    print("Invalid unit")
```

### Unit Compatibility Checking

```python
from usif import Units

# Check if units can be converted
unit1 = "eV"
unit2 = "J"
if Units.are_compatible(unit1, unit2):
    print("Units are compatible - can convert")
else:
    print("Units are incompatible")
```

### Property Definition with Units

```python
from usif import Units, PropertyDefinition, PropertyRegistry

# Define property with standard unit
energy_prop = PropertyDefinition(
    name="energy",
    data_type=float,
    units=Units.STANDARD_ENERGY,  # Uses Units.EV
    description="Total energy"
)

# Register property
PropertyRegistry.register(energy_prop)
```

## Implementation Details

### Unit String Storage

Units are stored as strings rather than objects for:
- Simplicity: Easy to serialize and store
- Flexibility: Can be extended without breaking changes
- Compatibility: Works with existing property systems

### Standard Unit Selection

Standard units are chosen based on:
- Common usage in computational materials science
- Compatibility with popular codes (VASP, Quantum ESPRESSO, etc.)
- Precision requirements
- Industry conventions

### Conversion Factor Precision

Conversion factors use appropriate precision:
- Exact values where possible (e.g., 1 nm = 10 Å)
- High precision for physical constants (e.g., J to eV)
- Appropriate significant figures for practical use

### Temperature Conversions

Temperature conversions use lambda functions because:
- Celsius and Fahrenheit require offset (not just multiplication)
- Lambda functions allow offset-based conversion
- Future: Can be replaced with proper conversion functions

## Testing Considerations

**Test Coverage Areas**:
- Unit constant values (verify all constants are defined)
- Unit validation (test is_valid_unit with valid/invalid units)
- Category detection (test get_unit_category for all units)
- Compatibility checking (test are_compatible with various pairs)
- Conversion factors (verify conversion factor accuracy)

**Important Test Cases**:
- All unit constants are valid strings
- Unit categories are correctly assigned
- Compatible units are correctly identified
- Conversion factors are accurate (compare with reference values)
- Edge cases (empty strings, None, invalid units)

## Future Enhancements

1. **Full Unit Conversion**: Implement complete conversion system using conversion factors
2. **Unit Parsing**: Parse complex unit strings (e.g., "kJ/mol", "m/s²")
3. **Unit Arithmetic**: Support unit operations (multiply, divide units)
4. **Dimensional Analysis**: Verify dimensional consistency in calculations
5. **Unit Display**: Format units for display (superscripts, subscripts)
6. **Custom Units**: Allow user-defined units with conversion factors
7. **Unit Validation in Properties**: Runtime validation of property values against units

## Related Modules

- **properties/registry.py**: Uses Units constants for built-in properties
- **properties/definitions.py**: PropertyDefinition stores unit strings from Units
- **constants.py**: Related constants (SymmetryConstants for tolerances)

