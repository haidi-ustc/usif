# Module: version.py

## Overview

The `version.py` module provides version information for the USIF package and binary format. It serves as the single source of truth for all version-related constants, ensuring consistency across the codebase. The module defines both package version (semantic versioning) and binary format version (integer).

**Purpose**: Centralize version information for package management, format compatibility checking, and version reporting.

**Role in Architecture**: Foundation layer - provides version constants used by encoder/decoder for format version checking and by package for version reporting.

## Architecture

The module is extremely simple, containing only module-level constants (no classes or functions). All version information is defined as constants that can be imported directly.

## Key Components

### Package Version

**__version__**: String representation of package version using semantic versioning (MAJOR.MINOR.PATCH)
- Current value: `"4.0"`
- Format: `"MAJOR.MINOR"` or `"MAJOR.MINOR.PATCH"`
- Used for: Package distribution, version reporting, dependency management

### Binary Format Version

**FORMAT_VERSION**: Integer representing the binary format version
- Current value: `4`
- Incremented when: Binary format changes (incompatible changes)
- Used for: Format compatibility checking, decoder version validation

### Version Tuple

**VERSION_INFO**: Tuple representation of version for programmatic access
- Current value: `(4, 0, 0)`
- Format: `(major, minor, patch)`
- Used for: Version comparison, programmatic version checking

### Version Components

Individual version components for convenience:
- `VERSION_MAJOR = 4`: Major version number
- `VERSION_MINOR = 0`: Minor version number
- `VERSION_PATCH = 0`: Patch version number

## Dependencies

**Internal Dependencies**: None - foundational module.

**External Dependencies**: None - uses only Python standard library.

**Used By**:
- `__init__.py`: Exports version information
- `encoder.py`: Uses FORMAT_VERSION for binary format header
- `decoder.py`: Uses FORMAT_VERSION for format validation
- Package setup: Uses __version__ for package metadata

## Data Structures

No data structures - only module-level constants (string, integer, tuple, integers).

## Usage Patterns

### Version Reporting

```python
from usif import __version__, FORMAT_VERSION

print(f"USIF package version: {__version__}")
print(f"Binary format version: {FORMAT_VERSION}")
```

### Format Version Checking

```python
from usif import FORMAT_VERSION
from usif.encoder import USIF

# Check format version during encoding
encoder = USIF()
# Format version is automatically written to binary header

# Check format version during decoding
# Decoder validates format version matches FORMAT_VERSION
```

### Version Comparison

```python
from usif import VERSION_INFO

# Compare versions programmatically
current_version = VERSION_INFO
required_version = (4, 0, 0)

if current_version >= required_version:
    print("Version is compatible")
```

### Package Metadata

```python
# In setup.py or pyproject.toml
from usif.version import __version__

setup(
    name="usif",
    version=__version__,
    ...
)
```

## Implementation Details

### Version Numbering Scheme

**Package Version (__version__)**:
- Uses semantic versioning: MAJOR.MINOR.PATCH
- MAJOR: Incompatible API changes
- MINOR: Backward-compatible functionality additions
- PATCH: Backward-compatible bug fixes
- Current: 4.0 (no patch number, equivalent to 4.0.0)

**Format Version (FORMAT_VERSION)**:
- Integer incremented for binary format changes
- Incremented when: Format structure changes, breaking compatibility
- Not incremented for: Bug fixes, optimizations that don't change format
- Current: 4

### Version Synchronization

Package version and format version are related but independent:
- Format version 4 corresponds to package version 4.0
- Format version changes less frequently than package version
- Package can have multiple patch versions with same format version

### Single Source of Truth

All version information is defined in this module:
- Prevents version inconsistencies
- Easy to update (single location)
- Imported by all modules that need version info

## Testing Considerations

**Test Coverage Areas**:
- Version constant values (verify they're set correctly)
- Version format (verify semantic versioning format)
- Version consistency (verify package and format versions are consistent)
- Version import (verify versions can be imported)

**Important Test Cases**:
- __version__ is valid semantic version string
- FORMAT_VERSION is positive integer
- VERSION_INFO tuple matches __version__ string
- Version components match VERSION_INFO
- Version can be imported from package root

## Future Enhancements

1. **Version History**: Track version history and changelog
2. **Compatibility Matrix**: Define compatibility between format versions
3. **Migration Tools**: Tools for converting between format versions
4. **Version Validation**: Runtime validation of version compatibility
5. **Version Metadata**: Additional metadata (release date, changes, etc.)

## Related Modules

- **__init__.py**: Exports version information to package API
- **encoder.py**: Uses FORMAT_VERSION in binary header
- **decoder.py**: Validates FORMAT_VERSION during decoding

