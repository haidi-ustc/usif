# Module: exceptions.py

## Overview

The `exceptions.py` module defines the exception hierarchy for the USIF format system. All exceptions inherit from a base `USIFError` class, allowing for both specific error handling and generic error catching. The hierarchy is designed to provide clear error categorization while maintaining simplicity.

**Purpose**: Provide a structured exception system for error handling throughout the USIF codebase, enabling both specific and generic error handling patterns.

**Role in Architecture**: Foundation layer - provides error handling infrastructure used by all modules that may raise exceptions.

## Architecture

The module defines a simple exception hierarchy:

```
USIFError (base)
├── EncodingError
├── DecodingError
│   └── CorruptedDataError
├── ValidationError
├── SymmetryAnalysisError
└── StorageError
```

All exceptions are simple classes inheriting from Python's `Exception` class (via USIFError), with no additional attributes or methods. This keeps the exception system lightweight while providing clear categorization.

## Key Components

### USIFError (Base Exception)

Base exception class for all USIF-related errors. All other exceptions inherit from this class.

**Purpose**: Allows catching all USIF errors with a single exception handler.

**Usage**:
```python
from usif import USIFError

try:
    structure.save('file.usif')
except USIFError as e:
    print(f"USIF error occurred: {e}")
```

**Design Rationale**: Provides a common base for all USIF exceptions, enabling generic error handling while maintaining specific exception types for detailed error handling.

### EncodingError

Raised when errors occur during encoding (structure to binary conversion).

**Raised By**:
- `encoder.py`: USIF.encode() method
- `properties/serializer.py`: PropertySerializer.serialize_value()
- `structures/structure.py`: USIFStructure.save() method

**Common Causes**:
- Invalid structure data
- Serialization failures
- Property encoding errors
- File I/O errors during save

**Usage**:
```python
from usif import EncodingError, USIFStructure

try:
    structure.save('file.usif')
except EncodingError as e:
    print(f"Encoding failed: {e}")
    # Handle encoding error
```

### DecodingError

Raised when errors occur during decoding (binary to structure conversion).

**Raised By**:
- `encoder.py`: USIF.decode() method
- `properties/serializer.py`: PropertySerializer.deserialize_value()
- `structures/structure.py`: USIFStructure.load() method

**Common Causes**:
- Invalid binary data
- Format version mismatch
- Deserialization failures
- File I/O errors during load

**Usage**:
```python
from usif import DecodingError, USIFStructure

try:
    structure = USIFStructure.load('file.usif')
except DecodingError as e:
    print(f"Decoding failed: {e}")
    # Handle decoding error
```

### CorruptedDataError

Specialized `DecodingError` raised when data corruption is detected.

**Raised By**:
- `encoder.py`: When hash verification fails
- `encoder.py`: When header validation fails
- `encoder.py`: When data integrity checks fail

**Common Causes**:
- Hash mismatch (data corruption)
- Invalid magic bytes
- Format version incompatibility
- Truncated or malformed data

**Usage**:
```python
from usif import CorruptedDataError, USIFStructure

try:
    structure = USIFStructure.load('file.usif')
except CorruptedDataError as e:
    print(f"Data corruption detected: {e}")
    # Handle corruption - may need to re-download or regenerate
except DecodingError as e:
    print(f"Other decoding error: {e}")
```

**Design Rationale**: Distinguishes between general decoding errors and data corruption, allowing different handling strategies (corruption may indicate file system issues or transmission errors).

### ValidationError

Raised when structure or property validation fails.

**Raised By**:
- `structures/structure.py`: USIFStructure validation methods
- `properties/definitions.py`: PropertyDefinition.validate_value()
- `converter.py`: Structure conversion validation

**Common Causes**:
- Invalid structure configuration (e.g., crystal without lattice)
- Property value out of range
- Type mismatches
- Dimensional inconsistencies

**Usage**:
```python
from usif import ValidationError, USIFStructure

try:
    structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        # Missing required lattice_matrix
        ...
    )
except ValidationError as e:
    print(f"Validation failed: {e}")
    # Fix structure configuration
```

### SymmetryAnalysisError

Raised when symmetry analysis fails.

**Raised By**:
- `converter.py`: StructureConverter symmetry analysis
- `utils/optimizer.py`: USIFOptimizer symmetry detection

**Common Causes**:
- pymatgen symmetry analyzer failures
- Invalid structure for symmetry analysis
- Tolerance issues
- Missing dependencies (pymatgen)

**Usage**:
```python
from usif import SymmetryAnalysisError, StructureConverter

try:
    usif_struct = StructureConverter.from_pymatgen(pmg_struct)
except SymmetryAnalysisError as e:
    print(f"Symmetry analysis failed: {e}")
    # Fall back to FULL_ATOMIC mode or handle error
```

### StorageError

Raised when container or storage operations fail.

**Raised By**:
- `container.py`: StructureContainer operations
- `container.py`: File I/O operations
- `container.py`: Index operations

**Common Causes**:
- Container file corruption
- Index corruption
- File system errors
- Concurrent access issues
- Invalid container operations

**Usage**:
```python
from usif import StorageError, StructureContainer

try:
    with StructureContainer('database.usifc', mode='w') as container:
        container.add(structure, name='test')
except StorageError as e:
    print(f"Storage operation failed: {e}")
    # Handle storage error
```

## Dependencies

**Internal Dependencies**: None - foundational module.

**External Dependencies**: None - uses only Python standard library (`Exception`).

**Used By**: All modules that raise exceptions:
- `encoder.py`
- `decoder.py` (via encoder)
- `structures/structure.py`
- `properties/serializer.py`
- `properties/definitions.py`
- `converter.py`
- `container.py`
- `utils/optimizer.py`

## Data Structures

No data structures - only exception class definitions.

## Usage Patterns

### Generic Error Handling

```python
from usif import USIFError

try:
    # USIF operations
    structure.save('file.usif')
    loaded = USIFStructure.load('file.usif')
except USIFError as e:
    # Catch any USIF error
    logger.error(f"USIF operation failed: {e}")
```

### Specific Error Handling

```python
from usif import EncodingError, DecodingError, ValidationError

try:
    structure.save('file.usif')
except EncodingError as e:
    # Handle encoding-specific issues
    print(f"Encoding failed: {e}")
except ValidationError as e:
    # Handle validation issues
    print(f"Invalid structure: {e}")
```

### Hierarchical Error Handling

```python
from usif import CorruptedDataError, DecodingError, USIFError

try:
    structure = USIFStructure.load('file.usif')
except CorruptedDataError as e:
    # Most specific - handle corruption
    print(f"Data corrupted: {e}")
    # Attempt recovery or re-download
except DecodingError as e:
    # More general - handle other decoding issues
    print(f"Decoding failed: {e}")
except USIFError as e:
    # Most general - catch any USIF error
    print(f"USIF error: {e}")
```

## Implementation Details

### Exception Design Philosophy

The exception system follows these principles:

1. **Simplicity**: No additional attributes or methods - just exception types
2. **Hierarchy**: Clear inheritance for both specific and generic handling
3. **Clarity**: Descriptive names that indicate error source
4. **Extensibility**: Easy to add new exception types if needed

### Error Messages

Error messages are provided by the raising code, not the exception classes themselves. This allows:
- Context-specific error messages
- Detailed debugging information
- Localization if needed

Example:
```python
raise EncodingError(f"Failed to serialize property '{prop_name}': {error_details}")
```

### Exception Chaining

Python's exception chaining is used to preserve original error context:

```python
try:
    # Operation that may fail
    data = struct.pack(format_str, value)
except struct.error as e:
    raise EncodingError(f"Failed to encode value: {e}") from e
```

## Testing Considerations

**Test Coverage Areas**:
- Exception inheritance (verify hierarchy)
- Exception raising (test all raise points)
- Exception catching (test specific and generic handlers)
- Exception messages (verify informative messages)

**Important Test Cases**:
- Verify exceptions are raised at appropriate points
- Test exception hierarchy (isinstance checks)
- Test exception messages contain useful information
- Test exception chaining preserves context

## Future Enhancements

1. **Exception Attributes**: Add optional attributes for error codes or context
2. **Error Codes**: Standardized error codes for programmatic handling
3. **Exception Context**: Add context managers for error context
4. **Error Recovery**: Add recovery strategies for specific error types
5. **Error Logging**: Integration with logging system for automatic error logging

## Related Modules

- **encoder.py**: Primary user of EncodingError and DecodingError
- **structures/structure.py**: Uses ValidationError
- **properties/serializer.py**: Uses EncodingError and DecodingError
- **converter.py**: Uses SymmetryAnalysisError and ValidationError
- **container.py**: Uses StorageError

