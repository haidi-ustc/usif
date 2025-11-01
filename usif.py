#!/usr/bin/env python3
"""
USIF (Universal Structure Interchange Format)
Unified format for crystals and molecules with intelligent compression

Features:
- Unified interface for periodic and non-periodic structures
- Intelligent compression: symmetric (crystals + molecules) or atomic (all types)
- Point group symmetry support for molecules
- Space group symmetry support for crystals
- Modular property system with type safety
- Random access container

Author: haidi@hfut.edu.cn
Version: 4.0
"""
import math
import struct
import hashlib
import gzip
import numpy as np
from typing import Dict, List, Tuple, Optional, Union, Any, Iterator, TypeVar, Generic
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from collections import defaultdict, OrderedDict
import queue
import mmap
import threading
import logging
from monty.json import MSONable

from pymatgen.core import Structure as PMGStructure, Lattice, Element
from pymatgen.core import Molecule as PMGMolecule
from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar, Vasprun
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer, PointGroupAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Binary Format Constants
# ============================================================================

class BinaryFormat:
    """Constants for struct pack/unpack format strings with explicit endianness"""
    # Unsigned integers - all explicit little-endian
    UINT8 = '<B'
    UINT16 = '<H'
    UINT32 = '<I'
    UINT64 = '<Q'

    # Signed integers - all explicit little-endian
    INT8 = '<b'
    INT16 = '<h'
    INT32 = '<i'
    INT64 = '<q'

    # Floating point - all explicit little-endian
    FLOAT32 = '<f'
    FLOAT64 = '<d'

    # Boolean
    BOOL = '<?'

    # Special flags
    LONG_COUNT_FLAG = 0xFF  # 255 indicates long format
    NULL_FLAG = 0xFE        # 254 indicates null value
    NAN_FLAG = 0xFD         # 253 indicates NaN value

    # Arrays
    @staticmethod
    def array(fmt: str, count: int) -> str:
        """Create array format string"""
        clean_fmt = fmt.lstrip('@=<>!')
        return f'{count}{clean_fmt}'

# ============================================================================
# Exceptions
# ============================================================================

class USIFError(Exception):
    """Base exception for USIF"""
    pass


class EncodingError(USIFError):
    """Error during encoding"""
    pass


class DecodingError(USIFError):
    """Error during decoding"""
    pass


class ValidationError(USIFError):
    """Validation error"""
    pass


class CorruptedDataError(DecodingError):
    """Corrupted data error"""
    pass


class SymmetryAnalysisError(USIFError):
    """Symmetry analysis error"""
    pass


class StorageError(USIFError):
    """Storage error"""
    pass


# ============================================================================
# Enums
# ============================================================================

class StructureType(IntEnum):
    """Structure type enumeration"""
    PERIODIC = 0  # Crystal with lattice
    MOLECULAR = 1  # Molecule without lattice


class StorageMode(IntEnum):
    """Storage mode enumeration"""
    SYMMETRIC = 0  # Symmetric storage (Wyckoff/point group)
    FULL_ATOMIC = 1  # Full atomic storage


class CompressionType(IntEnum):
    """Compression type enumeration"""
    NONE = 0
    GZIP = 1


# ============================================================================
# Property System - Modular Architecture
# ============================================================================

T = TypeVar('T')

@dataclass
class PropertyDefinition(Generic[T]):
    """Generic property definition with type parameter"""
    
    name: str
    data_type: type
    is_per_atom: bool = False
    dimensions: Tuple[int, ...] = ()
    description: str = ""
    units: str = ""
    required: bool = False
    default_value: Optional[T] = None
    
    # Type constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[T]] = None

    def is_scalar(self) -> bool:
        return len(self.dimensions) == 0

    def validate_value(self, value: Any, num_atoms: Optional[int] = None) -> Tuple[bool, str]:
        """Enhanced validation with range and value checks"""
        
        # Basic validation
        is_valid, message = self._basic_validation(value, num_atoms)
        if not is_valid:
            return False, message

        # Range validation for numeric types
        if self.min_value is not None or self.max_value is not None:
            range_error = self._validate_range(value)
            if range_error:
                return False, range_error

        # Allowed values validation
        if self.allowed_values is not None:
            if value not in self.allowed_values:
                return False, f"Value {value} not in allowed values {self.allowed_values}"

        return True, "Validation passed"

    def _basic_validation(self, value: Any, num_atoms: Optional[int] = None) -> Tuple[bool, str]:
        """Perform basic type and shape validation"""
        if value is None:
            if self.required:
                return False, "Value is required but None provided"
            return True, "Optional value is None"

        if not isinstance(value, self.data_type):
            return False, f"Expected type {self.data_type}, got {type(value)}"

        # Shape validation
        expected_shape = self.get_expected_shape(num_atoms)
        if expected_shape:
            shape_error = self._validate_shape(value, expected_shape)
            if shape_error:
                return False, shape_error

        return True, "Basic validation passed"

    def _validate_range(self, value: Any) -> Optional[str]:
        """Validate numeric range"""
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                return f"Value {value} below minimum {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return f"Value {value} above maximum {self.max_value}"
        
        # For arrays, validate each element
        elif hasattr(value, '__iter__') and not isinstance(value, str):
            for i, elem in enumerate(value):
                elem_error = self._validate_range(elem)
                if elem_error:
                    return f"Element {i}: {elem_error}"
        
        return None

    def _validate_shape(self, value: Any, expected_shape: Tuple[int, ...]) -> Optional[str]:
        """Validate array shape"""
        if hasattr(value, 'shape'):  # numpy array
            if value.shape != expected_shape:
                return f"Expected shape {expected_shape}, got {value.shape}"
        elif hasattr(value, '__len__'):
            if len(value) != expected_shape[0]:
                return f"Expected length {expected_shape[0]}, got {len(value)}"
            # Recursively check nested dimensions
            if len(expected_shape) > 1 and hasattr(value[0], '__len__'):
                for i, elem in enumerate(value):
                    elem_error = self._validate_shape(elem, expected_shape[1:])
                    if elem_error:
                        return f"Element {i}: {elem_error}"
        return None

    def get_expected_shape(self, num_atoms: Optional[int] = None) -> Tuple[int, ...]:
        """Get expected shape for validation"""
        if self.is_per_atom and num_atoms is not None:
            return (num_atoms,) + self.dimensions
        return self.dimensions


class PropertySerializer:
    """Serialize and deserialize property values with clear structure vs per-atom distinction"""
    
    # Constants for efficient count encoding
    SINGLE_VALUE_FLAG = 0  # Indicates single value repeated for all atoms
    LONG_COUNT_FLAG = 255  # Indicates 4-byte count follows
    
    TYPE_HANDLERS = {
        float: {
            'scalar_format': BinaryFormat.FLOAT64,
            'array_format': BinaryFormat.FLOAT32,
            'scalar_size': 8,
            'element_size': 4
        },
        int: {
            'scalar_format': BinaryFormat.INT64, 
            'array_format': BinaryFormat.INT32,
            'scalar_size': 8,
            'element_size': 4
        },
        bool: {
            'scalar_format': BinaryFormat.BOOL,
            'array_format': BinaryFormat.BOOL,
            'scalar_size': 1,
            'element_size': 1
        },
        str: {
            'scalar_format': None,
            'array_format': None,
            'scalar_size': lambda x: PropertySerializer._get_string_size(x),
            'element_size': lambda x: PropertySerializer._get_string_size(x)
        },
        tuple: {
            'scalar_format': None,
            'array_format': BinaryFormat.FLOAT32,
            'scalar_size': lambda dim: dim * 4,
            'element_size': lambda dim: dim * 4
        }
    }
    
    @staticmethod
    def _get_string_size(value: str) -> int:
        """Calculate encoded string size"""
        encoded_len = len(value.encode('utf-8'))
        return 1 + encoded_len if encoded_len <= 255 else 5 + encoded_len
    
    @staticmethod
    def _is_sequence(value: Any) -> bool:
        """Check if value is a sequence (but not string)"""
        return hasattr(value, '__len__') and not isinstance(value, (str, bytes))

    @staticmethod
    def _get_atom_count(value: Any, num_atoms: Optional[int]) -> int:
        """Get actual count of values for per-atom properties"""
        if PropertySerializer._is_sequence(value) and not PropertySerializer._is_multi_dimensional_element(value):
            return len(value)
        return 1
    
    
    @staticmethod
    def serialize_value(value: Any, prop_def: PropertyDefinition,
                       num_atoms: Optional[int] = None) -> bytes:
        """Serialize property value to bytes"""
        if value is None:
            return b''
        
        try:
            if prop_def.is_scalar():
                return PropertySerializer._serialize_scalar(value, prop_def)
            else:
                return PropertySerializer._serialize_array(value, prop_def, num_atoms)
        except (struct.error, UnicodeEncodeError, ValueError) as e:
            raise EncodingError(f"Failed to serialize property '{prop_def.name}': {e}") from e
    
    @staticmethod
    def _serialize_scalar(value: Any, prop_def: PropertyDefinition) -> bytes:
        """Serialize scalar value"""
        handler = PropertySerializer.TYPE_HANDLERS.get(prop_def.data_type)
        if not handler:
            raise EncodingError(f"Unsupported scalar type: {prop_def.data_type}")
        
        if prop_def.data_type == str:
            return PropertySerializer._serialize_string(value)
        
        fmt = handler['scalar_format']
        if fmt:
            return struct.pack(fmt, value)
        raise EncodingError(f"Scalar format not defined for {prop_def.data_type}")
    
    @staticmethod
    def _serialize_array(value: Any, prop_def: PropertyDefinition,
                        num_atoms: Optional[int] = None) -> bytes:
        """Serialize array value - handles both structure arrays and per-atom arrays"""
        data = bytearray()
        
        if prop_def.is_per_atom:
            # PER-ATOM PROPERTY: Store multiple values (one per atom)
            PropertySerializer._serialize_per_atom_array(data, value, prop_def, num_atoms)
        else:
            # STRUCTURE PROPERTY: Store single array value  
            PropertySerializer._serialize_structure_array(data, value, prop_def)
        
        return bytes(data)
    
    @staticmethod
    def _serialize_per_atom_array(data: bytearray, value: Any, 
                                 prop_def: PropertyDefinition, num_atoms: Optional[int]) -> None:
        """Serialize per-atom property (multiple values, one per atom)"""
        # Check if this is a single multi-dimensional element (like one force vector)
        if PropertySerializer._is_multi_dimensional_element(value) and prop_def.dimensions:
            # Single multi-dimensional element for one atom
            actual_count = 1
        else:
            actual_count = PropertySerializer._get_atom_count(value, num_atoms)
        
        # Validate count consistency
        if num_atoms is not None and actual_count != 1 and actual_count != num_atoms:
            raise EncodingError(
                f"Per-atom property count mismatch: expected 1 or {num_atoms}, got {actual_count}"
            )
        
        # Encode count information
        if actual_count == 1 and not PropertySerializer._is_sequence(value):
            # Single scalar value repeated for all atoms - use special flag
            data.extend(struct.pack(BinaryFormat.UINT8, PropertySerializer.SINGLE_VALUE_FLAG))
            element_data = PropertySerializer._serialize_array_element(value, prop_def)
            data.extend(element_data)
        elif actual_count == 1 and PropertySerializer._is_multi_dimensional_element(value):
            # Single multi-dimensional element (like force vector) for one atom
            data.extend(struct.pack(BinaryFormat.UINT8, PropertySerializer.SINGLE_VALUE_FLAG))
            element_data = PropertySerializer._serialize_array_element(value, prop_def)
            data.extend(element_data)
        else:
            # Multiple values - encode actual count
            if actual_count <= PropertySerializer.LONG_COUNT_FLAG - 1:
                data.extend(struct.pack(BinaryFormat.UINT8, actual_count))
            else:
                data.extend(struct.pack(BinaryFormat.UINT8, PropertySerializer.LONG_COUNT_FLAG))
                data.extend(struct.pack(BinaryFormat.UINT32, actual_count))
            
            # Serialize each value
            if PropertySerializer._is_sequence(value) and not PropertySerializer._is_multi_dimensional_element(value):
                for atom_value in value:
                    element_data = PropertySerializer._serialize_array_element(atom_value, prop_def)
                    data.extend(element_data)
            else:
                # Should not happen due to count check above
                raise EncodingError("Invalid per-atom value structure")
    
    @staticmethod
    def _serialize_structure_array(data: bytearray, value: Any,
                                  prop_def: PropertyDefinition) -> None:
        """Serialize structure-level array property (single array value)"""
        element_data = PropertySerializer._serialize_array_element(value, prop_def)
        data.extend(element_data)
    
    @staticmethod
    def _serialize_array_element(value: Any, prop_def: PropertyDefinition) -> bytes:
        """Serialize a single array element (could be scalar or multi-dimensional)"""
        if prop_def.dimensions:
            # Multi-dimensional array element
            return PropertySerializer._serialize_multi_dimensional(value, prop_def)
        else:
            # Scalar array element
            return PropertySerializer._serialize_scalar_element(value, prop_def)
    
    @staticmethod
    def _serialize_multi_dimensional(value: Any, prop_def: PropertyDefinition) -> bytes:
        """Serialize multi-dimensional array element"""
        dim = prop_def.dimensions[0]
        
        # Validate dimensions - allow single multi-dimensional elements
        if not PropertySerializer._is_sequence(value) or len(value) != dim:
            if PropertySerializer._is_multi_dimensional_element(value) and len(value) == dim:
                # This is a valid multi-dimensional element
                pass
            else:
                raise EncodingError(f"Dimension mismatch: expected {dim}, got {len(value) if PropertySerializer._is_sequence(value) else 'scalar'}")
        
        if prop_def.data_type in (float, tuple):
            return struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, dim), *value)
        elif prop_def.data_type == int:
            return struct.pack(BinaryFormat.array(BinaryFormat.INT32, dim), *value)
        elif prop_def.data_type == bool:
            bool_bytes = [1 if x else 0 for x in value]
            return struct.pack(BinaryFormat.array(BinaryFormat.UINT8, dim), *bool_bytes)
        else:
            raise EncodingError(f"Unsupported multi-dimensional type: {prop_def.data_type}")
    
    @staticmethod
    def _serialize_scalar_element(value: Any, prop_def: PropertyDefinition) -> bytes:
        """Serialize scalar array element"""
        handler = PropertySerializer.TYPE_HANDLERS.get(prop_def.data_type)
        if not handler:
            raise EncodingError(f"Unsupported array element type: {prop_def.data_type}")
        
        if prop_def.data_type == str:
            return PropertySerializer._serialize_string(value)
        
        fmt = handler['array_format']
        if fmt:
            return struct.pack(fmt, value)
        raise EncodingError(f"Array format not defined for {prop_def.data_type}")
    
    @staticmethod
    def _serialize_string(value: str) -> bytes:
        """Serialize string with efficient length encoding"""
        encoded = value.encode('utf-8')
        encoded_len = len(encoded)
        
        if encoded_len <= 255:
            return struct.pack(BinaryFormat.UINT8, encoded_len) + encoded
        else:
            return struct.pack(BinaryFormat.UINT8, PropertySerializer.LONG_COUNT_FLAG) + \
                   struct.pack(BinaryFormat.UINT32, encoded_len) + encoded

    @staticmethod
    def deserialize_value(prop_def: PropertyDefinition, data: bytes,
                         offset: int, num_atoms: Optional[int] = None) -> Tuple[Any, int]:
        """Deserialize property value from bytes"""
        if len(data) <= offset:
            return None, offset
        
        try:
            if prop_def.is_scalar():
                return PropertySerializer._deserialize_scalar(data, offset, prop_def)
            else:
                return PropertySerializer._deserialize_array(data, offset, prop_def, num_atoms)
        except (struct.error, UnicodeDecodeError, ValueError) as e:
            raise DecodingError(f"Failed to deserialize property '{prop_def.name}' at offset {offset}: {e}") from e

    @staticmethod
    def _deserialize_scalar(data: bytes, offset: int, prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize scalar value"""
        handler = PropertySerializer.TYPE_HANDLERS.get(prop_def.data_type)
        if not handler:
            raise DecodingError(f"Unsupported scalar data type: {prop_def.data_type}")
        
        if prop_def.data_type == str:
            return PropertySerializer._deserialize_string(data, offset)
        
        fmt = handler['scalar_format']
        if fmt:
            size = struct.calcsize(fmt)
            value = struct.unpack(fmt, data[offset:offset+size])[0]
            return value, offset + size
        raise DecodingError(f"Scalar format not defined for {prop_def.data_type}")
    
    @staticmethod
    def _deserialize_array(data: bytes, offset: int, prop_def: PropertyDefinition,
                          num_atoms: Optional[int] = None) -> Tuple[Any, int]:
        """Deserialize array value"""
        if prop_def.is_per_atom:
            return PropertySerializer._deserialize_per_atom_array(data, offset, prop_def, num_atoms)
        else:
            return PropertySerializer._deserialize_structure_array(data, offset, prop_def)
    
    @staticmethod
    def _deserialize_per_atom_array(data: bytes, offset: int, prop_def: PropertyDefinition,
                                   num_atoms: Optional[int]) -> Tuple[Any, int]:
        """Deserialize per-atom property"""
        # Read count flag/byte
        count_flag = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
        offset += 1
        
        if count_flag == PropertySerializer.SINGLE_VALUE_FLAG:
            # Single value repeated for all atoms
            value, offset = PropertySerializer._deserialize_array_element(data, offset, prop_def)
            if num_atoms and num_atoms > 1:
                return [value] * num_atoms, offset
            else:
                # For single atom, return just the value (not a list)
                return value, offset
        else:
            # Multiple values
            if count_flag == PropertySerializer.LONG_COUNT_FLAG:
                count = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
            else:
                count = count_flag
            
            # Validate count consistency
            if num_atoms is not None and count != num_atoms:
                raise DecodingError(
                    f"Per-atom property count mismatch: expected {num_atoms}, got {count}"
                )
            
            values = []
            for _ in range(count):
                atom_value, offset = PropertySerializer._deserialize_array_element(data, offset, prop_def)
                values.append(atom_value)
            
            return values, offset

    @staticmethod
    def _deserialize_structure_array(data: bytes, offset: int,
                                    prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize structure-level array property"""
        return PropertySerializer._deserialize_array_element(data, offset, prop_def)
    
    @staticmethod
    def _deserialize_array_element(data: bytes, offset: int,
                                  prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize single array element"""
        if prop_def.dimensions:
            return PropertySerializer._deserialize_multi_dimensional(data, offset, prop_def)
        else:
            return PropertySerializer._deserialize_scalar_element(data, offset, prop_def)
    
    @staticmethod
    def _deserialize_multi_dimensional(data: bytes, offset: int,
                                      prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize multi-dimensional array element"""
        dim = prop_def.dimensions[0]
        
        if prop_def.data_type in (float, tuple):
            size = dim * 4
            values = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, dim),
                                 data[offset:offset+size])
            return tuple(values), offset + size
        elif prop_def.data_type == int:
            size = dim * 4
            values = struct.unpack(BinaryFormat.array(BinaryFormat.INT32, dim),
                                 data[offset:offset+size])
            return tuple(values), offset + size
        elif prop_def.data_type == bool:
            bool_values = struct.unpack(BinaryFormat.array(BinaryFormat.UINT8, dim),
                                      data[offset:offset+dim])
            return tuple(bool(x) for x in bool_values), offset + dim
        else:
            raise DecodingError(f"Unsupported multi-dimensional type: {prop_def.data_type}")
    
    @staticmethod
    def _deserialize_scalar_element(data: bytes, offset: int,
                                   prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize scalar array element"""
        handler = PropertySerializer.TYPE_HANDLERS.get(prop_def.data_type)
        if not handler:
            raise DecodingError(f"Unsupported array element type: {prop_def.data_type}")
        
        if prop_def.data_type == str:
            return PropertySerializer._deserialize_string(data, offset)
        
        fmt = handler['array_format']
        if fmt:
            size = struct.calcsize(fmt)
            value = struct.unpack(fmt, data[offset:offset+size])[0]
            return value, offset + size
        raise DecodingError(f"Array format not defined for {prop_def.data_type}")
    
    @staticmethod
    def _deserialize_string(data: bytes, offset: int) -> Tuple[str, int]:
        """Deserialize string with efficient length encoding"""
        encoded_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
        offset += 1
        
        if encoded_len == PropertySerializer.LONG_COUNT_FLAG:
            encoded_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
            offset += 4
        
        value = data[offset:offset+encoded_len].decode('utf-8')
        return value, offset + encoded_len

    @staticmethod
    def _is_multi_dimensional_element(value: Any) -> bool:
        """Check if value is a multi-dimensional element (like force vector) rather than a list of elements"""
        if not PropertySerializer._is_sequence(value):
            return False
        
        # If it's a string, it's not a multi-dimensional element
        if isinstance(value, (str, bytes)):
            return False
        
        # If all elements are numbers, it's a multi-dimensional element
        if all(isinstance(x, (int, float)) for x in value):
            return True
        
        return False
    
    @staticmethod
    def _is_list_of_multi_dimensional_elements(value: Any) -> bool:
        """Check if value is a list of multi-dimensional elements"""
        if not PropertySerializer._is_sequence(value) or len(value) == 0:
            return False
        
        # Check if first element is a multi-dimensional element
        first_elem = value[0]
        return PropertySerializer._is_multi_dimensional_element(first_elem)
    
    @staticmethod
    def validate_value(value: Any, prop_def: PropertyDefinition, 
                      num_atoms: Optional[int] = None) -> bool:
        """Validate that a value matches the property definition"""
        if value is None:
            return True
        
        # Check basic type compatibility
        expected_type = prop_def.data_type
        if not isinstance(value, expected_type):
            # Allow tuple for float arrays with dimensions
            if not (expected_type == float and isinstance(value, tuple) and prop_def.dimensions):
                # Also allow numpy arrays for numerical data
                if isinstance(value, np.ndarray) and expected_type in (float, int, tuple):
                    pass
                # Allow lists/tuples of expected type for per-atom properties
                elif (prop_def.is_per_atom and 
                      isinstance(value, (list, tuple)) and 
                      len(value) > 0 and
                      num_atoms is not None and
                      num_atoms > 1):
                    # This could be a list of elements - will validate structure later
                    pass
                else:
                    return False
        
        # For per-atom properties, validate structure
        if prop_def.is_per_atom and not prop_def.is_scalar():
            if num_atoms is None:
                # If num_atoms is not specified, just validate the element structure
                return PropertySerializer._validate_element(value, prop_def)
            elif num_atoms == 1:
                # For single atom, accept either the element directly or a list with one element
                if isinstance(value, (list, tuple, np.ndarray)) and len(value) == 1:
                    return PropertySerializer._validate_element(value[0], prop_def)
                else:
                    return PropertySerializer._validate_element(value, prop_def)
            else:
                # For multiple atoms
                if PropertySerializer._is_multi_dimensional_element(value):
                    # Single multi-dimensional element that will be repeated for all atoms
                    return PropertySerializer._validate_element(value, prop_def)
                elif PropertySerializer._is_list_of_multi_dimensional_elements(value):
                    # List of multi-dimensional elements - check count
                    if len(value) == num_atoms:
                        return all(PropertySerializer._validate_element(elem, prop_def) for elem in value)
                    else:
                        # Wrong number of elements
                        return False
                elif isinstance(value, (list, tuple, np.ndarray)):
                    # Regular list of values - check count and each element
                    if len(value) == num_atoms:
                        return all(PropertySerializer._validate_element(elem, prop_def) for elem in value)
                    else:
                        return False
                else:
                    # Single scalar value that will be repeated for all atoms
                    return PropertySerializer._validate_element(value, prop_def)
        
        return PropertySerializer._validate_element(value, prop_def)

    @staticmethod
    def _validate_element(value: Any, prop_def: PropertyDefinition) -> bool:
        """Validate a single element (scalar or array element)"""
        if prop_def.dimensions:
            # For multi-dimensional elements, check dimensions and content
            if not isinstance(value, (tuple, list, np.ndarray)):
                return False
            if len(value) != prop_def.dimensions[0]:
                return False
            # For multi-dimensional elements, check that all elements are numbers
            if not all(isinstance(x, (int, float)) for x in value):
                return False
        
        # For scalar elements, we've already done type checking above
        return True

    @staticmethod
    def get_expected_size(prop_def: PropertyDefinition, value: Any = None, 
                         num_atoms: Optional[int] = None) -> int:
        """Calculate expected size in bytes for serialized property value"""
        if value is None:
            return 0
        
        handler = PropertySerializer.TYPE_HANDLERS.get(prop_def.data_type)
        if not handler:
            return 0
        
        if prop_def.is_scalar():
            if prop_def.data_type == str:
                return handler['scalar_size'](value)
            return handler['scalar_size']
        else:
            if prop_def.is_per_atom:
                # Check if this is a single multi-dimensional element
                if PropertySerializer._is_multi_dimensional_element(value) and prop_def.dimensions:
                    actual_count = 1
                else:
                    actual_count = PropertySerializer._get_atom_count(value, num_atoms)
                
                # Count encoding size
                count_size = 1  # Default to 1 byte for count
                if actual_count > PropertySerializer.LONG_COUNT_FLAG - 1:
                    count_size = 5  # 1 byte flag + 4 bytes count
                
                if actual_count is None:
                    return count_size
                
                # Calculate element size
                if prop_def.dimensions:
                    dim = prop_def.dimensions[0]
                    if prop_def.data_type in (float, tuple):
                        element_size = dim * 4
                    elif prop_def.data_type == int:
                        element_size = dim * 4
                    elif prop_def.data_type == bool:
                        element_size = dim
                    else:
                        element_size = 0
                else:
                    if prop_def.data_type == str:
                        # Estimate average string size
                        element_size = handler['element_size'](value[0]) if hasattr(value, '__getitem__') and value else 50
                    else:
                        element_size = handler['element_size']
                
                return count_size + (actual_count * element_size)
            else:
                if prop_def.dimensions:
                    dim = prop_def.dimensions[0]
                    if prop_def.data_type in (float, tuple):
                        return dim * 4
                    elif prop_def.data_type == int:
                        return dim * 4
                    elif prop_def.data_type == bool:
                        return dim
                else:
                    if prop_def.data_type == str:
                        return handler['element_size'](value)
                    return handler['element_size']
        
        return 0

class PropertyRegistry:
    """Registry of built-in property definitions"""
    
    _properties: Dict[str, PropertyDefinition] = {
        # Atomic properties
        'force': PropertyDefinition('force', tuple, is_per_atom=True, dimensions=(3,),
                                   description='Force on atom', units='eV/Å'),
        'charge': PropertyDefinition('charge', float, is_per_atom=True,
                                    description='Atomic charge', units='e'),
        'magmom': PropertyDefinition('magmom', float, is_per_atom=True,
                                    description='Magnetic moment', units='μB'),
        'velocity': PropertyDefinition('velocity', tuple, is_per_atom=True, dimensions=(3,),
                                      description='Atomic velocity', units='Å/fs'),
        
        # Structure properties
        'energy': PropertyDefinition('energy', float, description='Total energy', units='eV'),
        'stress': PropertyDefinition('stress', tuple, dimensions=(6,),
                                    description='Stress tensor (Voigt)', units='GPa'),
        'volume': PropertyDefinition('volume', float, description='Cell volume', units='Å³'),
        'pressure': PropertyDefinition('pressure', float, description='Pressure', units='GPa'),
        'temperature': PropertyDefinition('temperature', float, description='Temperature', units='K'),
    }
    
    @classmethod
    def register(cls, prop_def: PropertyDefinition) -> None:
        """Register a new property definition"""
        if prop_def.name in cls._properties:
            logger.warning(f"Overwriting existing property definition: {prop_def.name}")
        cls._properties[prop_def.name] = prop_def
    
    @classmethod
    def get(cls, name: str) -> Optional[PropertyDefinition]:
        """Get property definition by name"""
        return cls._properties.get(name)
    
    @classmethod
    def is_atomic_property(cls, name: str) -> bool:
        """Check if property is per-atom"""
        prop_def = cls.get(name)
        return prop_def.is_per_atom if prop_def else False
    
    @classmethod
    def is_structure_property(cls, name: str) -> bool:
        """Check if property is structure-level"""
        prop_def = cls.get(name)
        return not prop_def.is_per_atom if prop_def else False


@dataclass
class AtomicProperties:
    """Properties that can be attached to individual atoms"""
    force: Optional[Tuple[float, float, float]] = None
    charge: Optional[float] = None
    magmom: Optional[float] = None
    velocity: Optional[Tuple[float, float, float]] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def get_all_properties(self) -> Dict[str, Any]:
        """Get all properties as dictionary"""
        props = {}
        if self.force is not None:
            props['force'] = self.force
        if self.charge is not None:
            props['charge'] = self.charge
        if self.magmom is not None:
            props['magmom'] = self.magmom
        if self.velocity is not None:
            props['velocity'] = self.velocity
        props.update(self.custom)
        return props

    def __eq__(self, other):
        if not isinstance(other, AtomicProperties):
            return False
        
        def compare_tuples(t1, t2):
            if t1 is None and t2 is None:
                return True
            if t1 is None or t2 is None:
                return False
            
            # Handle numpy arrays
            if isinstance(t1, np.ndarray):
                t1 = tuple(t1)
            if isinstance(t2, np.ndarray):
                t2 = tuple(t2)
                
            if hasattr(t1, '__len__') and hasattr(t2, '__len__'):
                if len(t1) != len(t2):
                    return False
                return all(abs(float(a) - float(b)) < 1e-6 for a, b in zip(t1, t2))
            else:
                return abs(float(t1) - float(t2)) < 1e-6
        
        if not compare_tuples(self.force, other.force):
            return False
        if not compare_tuples(self.velocity, other.velocity):
            return False
        
        if self.charge is not None and other.charge is not None:
            if abs(float(self.charge) - float(other.charge)) > 1e-6:
                return False
        elif self.charge != other.charge:
            return False
        
        if self.magmom is not None and other.magmom is not None:
            if abs(float(self.magmom) - float(other.magmom)) > 1e-6:
                return False
        elif self.magmom != other.magmom:
            return False
        
        if self.custom != other.custom:
            return False
        
        return True


@dataclass
class StructureProperties:
    """Properties that can be attached to the entire structure"""
    energy: Optional[float] = None
    stress: Optional[Tuple[float, ...]] = None
    volume: Optional[float] = None
    pressure: Optional[float] = None
    temperature: Optional[float] = None
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def get_all_properties(self) -> Dict[str, Any]:
        """Get all properties as dictionary"""
        props = {}
        if self.energy is not None:
            props['energy'] = self.energy
        if self.stress is not None:
            props['stress'] = self.stress
        if self.volume is not None:
            props['volume'] = self.volume
        if self.pressure is not None:
            props['pressure'] = self.pressure
        if self.temperature is not None:
            props['temperature'] = self.temperature
        props.update(self.custom)
        return props
    
    
    def __eq__(self, other):
        if not isinstance(other, StructureProperties):
            return False
        
        def compare_values(v1, v2):
            if v1 is None and v2 is None:
                return True
            if v1 is None or v2 is None:
                return False
            
            # Handle numpy arrays and tuples
            if isinstance(v1, (tuple, list, np.ndarray)) and isinstance(v2, (tuple, list, np.ndarray)):
                if len(v1) != len(v2):
                    return False
                return all(abs(float(a) - float(b)) < 1e-6 for a, b in zip(v1, v2))
            elif isinstance(v1, float) and isinstance(v2, float):
                return abs(v1 - v2) < 1e-6
            else:
                return v1 == v2
        
        for prop_name in ['energy', 'volume', 'pressure', 'temperature']:
            v1 = getattr(self, prop_name, None)
            v2 = getattr(other, prop_name, None)
            if not compare_values(v1, v2):
                return False
        
        # Special handling for stress
        if not compare_values(self.stress, other.stress):
            return False
        
        if self.custom != other.custom:
            return False
        
        return True


@dataclass
class WyckoffSite:
    """Wyckoff position for symmetric storage (periodic only)"""
    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Fractional
    occupancy: float = 1.0
    
    def __eq__(self, other):
        if not isinstance(other, WyckoffSite):
            return False
        return (self.atomic_number == other.atomic_number and
                self.multiplicity == other.multiplicity and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                abs(self.occupancy - other.occupancy) < 1e-6)


@dataclass
class PointGroupSite:
    """Point group symmetric position for molecules"""
    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Cartesian (Å)
    occupancy: float = 1.0
    
    def __eq__(self, other):
        if not isinstance(other, PointGroupSite):
            return False
        return (self.atomic_number == other.atomic_number and
                self.multiplicity == other.multiplicity and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                abs(self.occupancy - other.occupancy) < 1e-6)


@dataclass
class AtomSite:
    """Universal atom site"""
    atomic_number: int
    coords: Tuple[float, float, float]
    properties: AtomicProperties = field(default_factory=AtomicProperties)
    
    def __eq__(self, other):
        if not isinstance(other, AtomSite):
            return False
        return (self.atomic_number == other.atomic_number and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                self.properties == other.properties)


class USIFStructure(MSONable):
    """
    Universal structure representation
    
    Structure type matrix:
    ┌─────────────┬──────────────┬─────────────────┐
    │             │ SYMMETRIC    │ FULL_ATOMIC     │
    ├─────────────┼──────────────┼─────────────────┤
    │ PERIODIC    │ Wyckoff      │ All atoms       │
    │ (Crystal)   │ + lattice    │ + lattice       │
    ├─────────────┼──────────────┼─────────────────┤
    │ MOLECULAR   │ Point group  │ All atoms       │
    │ (Molecule)  │ (no lattice) │ (no lattice)    │
    └─────────────┴──────────────┴─────────────────┘
    """
    
    __slots__ = ['structure_type', 'storage_mode', 'lattice_matrix', 'spacegroup', 
                'point_group', 'wyckoff_sites', 'point_group_sites', 'atom_sites',
                'structure_properties', 'formula']
    
    def __init__(self, 
                 structure_type: StructureType = StructureType.PERIODIC,
                 storage_mode: StorageMode = StorageMode.SYMMETRIC,
                 lattice_matrix: Optional[np.ndarray] = None,
                 spacegroup: int = 1,
                 point_group: Optional[str] = None,
                 wyckoff_sites: Optional[List[WyckoffSite]] = None,
                 point_group_sites: Optional[List[PointGroupSite]] = None,
                 atom_sites: Optional[List[AtomSite]] = None,
                 structure_properties: Optional[StructureProperties] = None,
                 formula: str = ""):
        
        self.structure_type = structure_type
        self.storage_mode = storage_mode
        self.lattice_matrix = lattice_matrix
        self.spacegroup = spacegroup
        self.point_group = point_group
        self.wyckoff_sites = wyckoff_sites
        self.point_group_sites = point_group_sites
        self.atom_sites = atom_sites
        self.structure_properties = structure_properties if structure_properties is not None \
                                    else StructureProperties()
        self.formula = formula
        
        self._validate_structure()
    
    def _validate_structure(self) -> None:
        """Validate structure configuration"""
        if self.structure_type == StructureType.MOLECULAR:
            if self.lattice_matrix is not None:
                raise ValidationError("Molecular structures should not have lattice")
            if self.storage_mode == StorageMode.SYMMETRIC and self.point_group_sites is None:
                raise ValidationError("Molecular SYMMETRIC mode requires point_group_sites")
            elif self.storage_mode == StorageMode.FULL_ATOMIC and self.atom_sites is None:
                raise ValidationError("Molecular FULL_ATOMIC mode requires atom_sites")
        else:
            if self.lattice_matrix is None:
                raise ValidationError("Periodic structures require lattice")
            if self.storage_mode == StorageMode.SYMMETRIC and self.wyckoff_sites is None:
                raise ValidationError("Periodic SYMMETRIC mode requires wyckoff_sites")
            elif self.storage_mode == StorageMode.FULL_ATOMIC and self.atom_sites is None:
                raise ValidationError("Periodic FULL_ATOMIC mode requires atom_sites")
    
    def is_periodic(self) -> bool:
        """Check if structure is periodic"""
        return self.structure_type == StructureType.PERIODIC
    
    def is_molecular(self) -> bool:
        """Check if structure is molecular"""
        return self.structure_type == StructureType.MOLECULAR
    
    def is_symmetric(self) -> bool:
        """Check if using symmetric storage"""
        return self.storage_mode == StorageMode.SYMMETRIC
    
    def num_atoms(self) -> int:
        """Get total number of atoms"""
        if self.storage_mode == StorageMode.SYMMETRIC:
            if self.is_periodic():
                return sum(site.multiplicity for site in self.wyckoff_sites)
            else:
                return sum(site.multiplicity for site in self.point_group_sites)
        else:
            return len(self.atom_sites)
    
    def as_dict(self) -> dict:
        """
        Convert USIFStructure to MSONable dictionary
        
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        d = {
            "@module": self.__class__.__module__,
            "@class": self.__class__.__name__,
            "structure_type": self.structure_type.value,
            "storage_mode": self.storage_mode.value,
            "spacegroup": self.spacegroup,
            "point_group": self.point_group,
            "structure_properties": self.structure_properties,
            "formula": self.formula
        }
        
        if self.lattice_matrix is not None:
            d["lattice_matrix"] = self.lattice_matrix.tolist()
        
        if self.wyckoff_sites is not None:
            d["wyckoff_sites"] = [{
                'atomic_number': site.atomic_number,
                'multiplicity': site.multiplicity,
                'coords': site.coords,
                'occupancy': site.occupancy
            } for site in self.wyckoff_sites]
        
        if self.point_group_sites is not None:
            d["point_group_sites"] = [{
                'atomic_number': site.atomic_number,
                'multiplicity': site.multiplicity,
                'coords': site.coords,
                'occupancy': site.occupancy
            } for site in self.point_group_sites]
        
        if self.atom_sites is not None:
            d["atom_sites"] = [{
                'atomic_number': site.atomic_number,
                'coords': site.coords,
                'properties': {
                    'force': site.properties.force,
                    'charge': site.properties.charge,
                    'magmom': site.properties.magmom,
                    'velocity': site.properties.velocity,
                    'custom': site.properties.custom
                }
            } for site in self.atom_sites]
        
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> 'USIFStructure':
        """
        Create USIFStructure from MSONable dictionary
        
        Args:
            d: Dictionary representation from as_dict()
            
        Returns:
            USIFStructure instance
        """
        lattice_matrix = None
        if "lattice_matrix" in d and d["lattice_matrix"] is not None:
            lattice_matrix = np.array(d["lattice_matrix"])
        
        wyckoff_sites = None
        if "wyckoff_sites" in d and d["wyckoff_sites"] is not None:
            wyckoff_sites = []
            for site_dict in d["wyckoff_sites"]:
                wyckoff_sites.append(WyckoffSite(**site_dict))
        
        point_group_sites = None
        if "point_group_sites" in d and d["point_group_sites"] is not None:
            point_group_sites = []
            for site_dict in d["point_group_sites"]:
                point_group_sites.append(PointGroupSite(**site_dict))
        
        atom_sites = None
        if "atom_sites" in d and d["atom_sites"] is not None:
            atom_sites = []
            for site_dict in d["atom_sites"]:
                props_dict = site_dict.get('properties', {})
                atom_props = AtomicProperties(
                    force=props_dict.get('force'),
                    charge=props_dict.get('charge'),
                    magmom=props_dict.get('magmom'),
                    velocity=props_dict.get('velocity'),
                    custom=props_dict.get('custom', {})
                )
                atom_sites.append(AtomSite(
                    atomic_number=site_dict['atomic_number'],
                    coords=site_dict['coords'],
                    properties=atom_props
                ))
        
        structure_properties = None
        if "structure_properties" in d:
            if isinstance(d["structure_properties"], dict):
                structure_properties = StructureProperties(**d["structure_properties"])
            else:
                structure_properties = d["structure_properties"]
        
        return cls(
            structure_type=StructureType(d["structure_type"]),
            storage_mode=StorageMode(d["storage_mode"]),
            lattice_matrix=lattice_matrix,
            spacegroup=d["spacegroup"],
            point_group=d.get("point_group"),
            wyckoff_sites=wyckoff_sites,
            point_group_sites=point_group_sites,
            atom_sites=atom_sites,
            structure_properties=structure_properties,
            formula=d["formula"]
        )
    
    def __eq__(self, other):
        if not isinstance(other, USIFStructure):
            return False
        
        lattice_equal = True
        if self.lattice_matrix is not None and other.lattice_matrix is not None:
            lattice_equal = np.allclose(self.lattice_matrix, other.lattice_matrix, atol=1e-6)
        elif self.lattice_matrix != other.lattice_matrix:
            lattice_equal = False
        
        return (self.structure_type == other.structure_type and
                self.storage_mode == other.storage_mode and
                lattice_equal and
                self.spacegroup == other.spacegroup and
                self.point_group == other.point_group and
                self.wyckoff_sites == other.wyckoff_sites and
                self.point_group_sites == other.point_group_sites and
                self.atom_sites == other.atom_sites and
                self.structure_properties == other.structure_properties and
                self.formula == other.formula)
    
    def __repr__(self):
        return (f"USIFStructure(structure_type={self.structure_type.name}, "
                f"storage_mode={self.storage_mode.name}, "
                f"formula='{self.formula}', "
                f"atoms={self.num_atoms()})")


# ============================================================================
# USIF Encoder/Decoder
# ============================================================================

class USIF:
    """USIF (Universal Structure Interchange Format) Encoder/Decoder"""
    
    VERSION = 4
    HEADER_SIZE = 64
    
    def __init__(self, compression: CompressionType = CompressionType.GZIP):
        self.compression = compression
    
    def _calculate_hash(self, structure: USIFStructure) -> bytes:
        """Calculate SHA-256 hash of structure"""
        data = bytearray()
        data.extend(struct.pack(BinaryFormat.UINT8, structure.structure_type.value))
        data.extend(struct.pack(BinaryFormat.UINT8, structure.storage_mode.value))
        
        if structure.is_periodic():
            lattice_data = structure.lattice_matrix.astype(np.float32).tobytes()
            data.extend(lattice_data)
            data.extend(struct.pack(BinaryFormat.UINT16, structure.spacegroup))
        elif structure.is_molecular() and structure.storage_mode == StorageMode.SYMMETRIC:
            pg_bytes = (structure.point_group or "C1").encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(pg_bytes)))
            data.extend(pg_bytes)
        
        if structure.storage_mode == StorageMode.SYMMETRIC:
            if structure.is_periodic():
                data.extend(struct.pack(BinaryFormat.UINT8, len(structure.wyckoff_sites)))
                for site in structure.wyckoff_sites:
                    data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                    coords = tuple(round(c, 5) for c in site.coords)
                    data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *coords))
            else:
                data.extend(struct.pack(BinaryFormat.UINT8, len(structure.point_group_sites)))
                for site in structure.point_group_sites:
                    data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                    coords = tuple(round(c, 5) for c in site.coords)
                    data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *coords))
        else:
            data.extend(struct.pack(BinaryFormat.UINT32, len(structure.atom_sites)))
            for site in structure.atom_sites:
                data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                coords = tuple(round(c, 5) for c in site.coords)
                data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *coords))
        
        return hashlib.sha256(bytes(data)).digest()
    
    def _compress_data(self, data: bytes) -> bytes:
        """Compress data based on compression type"""
        try:
            if self.compression == CompressionType.GZIP:
                return gzip.compress(data, compresslevel=6)
            return data
        except Exception as e:
            raise EncodingError(f"Compression failed: {e}") from e
    
    def _decompress_data(self, data: bytes, comp_type: CompressionType) -> bytes:
        """Decompress data based on compression type"""
        try:
            if comp_type == CompressionType.GZIP:
                return gzip.decompress(data)
            return data
        except gzip.BadGzipFile as e:
            raise CorruptedDataError(f"Corrupted gzip data: {e}") from e
        except Exception as e:
            raise DecodingError(f"Decompression failed: {e}") from e
    
    def _encode_atomic_properties(self, props: AtomicProperties, 
                                  num_atoms: Optional[int] = None) -> bytes:
        """Encode atomic properties using modular system"""
        data = bytearray()
        
        all_props = props.get_all_properties()
        built_in_props = list(PropertyRegistry._properties.keys())
        atomic_props = [p for p in built_in_props if PropertyRegistry.is_atomic_property(p)]
        
        present_props = [p for p in atomic_props if p in all_props]
        data.extend(struct.pack(BinaryFormat.UINT8, len(present_props)))
        
        for prop_name in present_props:
            prop_def = PropertyRegistry.get(prop_name)
            if prop_def is None:
                continue
            
            name_bytes = prop_name.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)
            
            prop_value = all_props[prop_name]
            prop_data = PropertySerializer.serialize_value(prop_value, prop_def, num_atoms)
            data.extend(struct.pack(BinaryFormat.UINT32, len(prop_data)))
            data.extend(prop_data)
        
        custom_props = {k: v for k, v in all_props.items() if k not in built_in_props}
        data.extend(struct.pack(BinaryFormat.UINT8, len(custom_props)))
        
        for custom_name, custom_value in custom_props.items():
            name_bytes = custom_name.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)
            
            value_str = str(custom_value)
            value_bytes = value_str.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
            data.extend(value_bytes)
        
        return bytes(data)
    
    def _decode_atomic_properties(self, data: bytes, offset: int, 
                                  num_atoms: Optional[int] = None) -> Tuple[AtomicProperties, int]:
        """Decode atomic properties using modular system"""
        props = AtomicProperties()
        
        try:
            num_props = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
            offset += 1
            
            for _ in range(num_props):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                offset += 1
                prop_name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                prop_def = PropertyRegistry.get(prop_name)
                if prop_def is None:
                    data_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                    offset += 4 + data_len
                    continue
                
                data_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
                
                prop_value, new_offset = PropertySerializer.deserialize_value(
                    prop_def, data, offset, num_atoms
                )
                offset = new_offset
                
                setattr(props, prop_name, prop_value)
            
            num_custom = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
            offset += 1
            
            for _ in range(num_custom):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                offset += 1
                custom_name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                value_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
                value_str = data[offset:offset+value_len].decode('utf-8')
                offset += value_len
                
                props.custom[custom_name] = value_str
            
            return props, offset
        except (struct.error, UnicodeDecodeError) as e:
            raise DecodingError(f"Failed to decode atomic properties at offset {offset}: {e}") from e
    
    def _encode_structure_properties(self, props: StructureProperties) -> bytes:
        """Encode structure properties using modular system"""
        data = bytearray()
        
        all_props = props.get_all_properties()
        built_in_props = list(PropertyRegistry._properties.keys())
        struct_props = [p for p in built_in_props if PropertyRegistry.is_structure_property(p)]
        
        present_props = [p for p in struct_props if p in all_props]
        data.extend(struct.pack(BinaryFormat.UINT8, len(present_props)))
        
        for prop_name in present_props:
            prop_def = PropertyRegistry.get(prop_name)
            if prop_def is None:
                continue
            
            name_bytes = prop_name.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)
            
            prop_value = all_props[prop_name]
            prop_data = PropertySerializer.serialize_value(prop_value, prop_def)
            data.extend(struct.pack(BinaryFormat.UINT32, len(prop_data)))
            data.extend(prop_data)
        
        custom_props = {k: v for k, v in all_props.items() if k not in built_in_props}
        data.extend(struct.pack(BinaryFormat.UINT8, len(custom_props)))
        
        for custom_name, custom_value in custom_props.items():
            name_bytes = custom_name.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)
            
            value_str = str(custom_value)
            value_bytes = value_str.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
            data.extend(value_bytes)
        
        return bytes(data)
    
    def _decode_structure_properties(self, data: bytes, 
                                    offset: int) -> Tuple[StructureProperties, int]:
        """Decode structure properties using modular system"""
        props = StructureProperties()
        
        try:
            num_props = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
            offset += 1
            
            for _ in range(num_props):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                offset += 1
                prop_name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                prop_def = PropertyRegistry.get(prop_name)
                if prop_def is None:
                    data_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                    offset += 4 + data_len
                    continue
                
                data_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
                
                prop_value, new_offset = PropertySerializer.deserialize_value(
                    prop_def, data, offset
                )
                offset = new_offset
                
                setattr(props, prop_name, prop_value)
            
            num_custom = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
            offset += 1
            
            for _ in range(num_custom):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                offset += 1
                custom_name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                value_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
                value_str = data[offset:offset+value_len].decode('utf-8')
                offset += value_len
                
                props.custom[custom_name] = value_str
            
            return props, offset
        except (struct.error, UnicodeDecodeError) as e:
            raise DecodingError(
                f"Failed to decode structure properties at offset {offset}: {e}"
            ) from e
    
    def encode(self, structure: USIFStructure) -> bytes:
        """
        Encode USIFStructure to bytes
        
        Args:
            structure: USIF structure to encode
            
        Returns:
            Encoded bytes
            
        Raises:
            EncodingError: If encoding fails
        """
        try:
            data = bytearray()
            
            data.extend(struct.pack(BinaryFormat.UINT8, structure.structure_type.value))
            data.extend(struct.pack(BinaryFormat.UINT8, structure.storage_mode.value))
            
            if structure.structure_type == StructureType.MOLECULAR:
                if structure.storage_mode == StorageMode.SYMMETRIC:
                    point_group = structure.point_group or "C1"
                    pg_bytes = point_group.encode('utf-8')
                    data.extend(struct.pack(BinaryFormat.UINT8, len(pg_bytes)))
                    data.extend(pg_bytes)
                    
                    data.extend(struct.pack(BinaryFormat.UINT8, len(structure.point_group_sites)))
                    for site in structure.point_group_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.UINT16, site.multiplicity))
                        data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                              *site.coords))
                        data.extend(struct.pack(BinaryFormat.FLOAT32, site.occupancy))
                else:
                    data.extend(struct.pack(BinaryFormat.UINT32, len(structure.atom_sites)))
                    for site in structure.atom_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                              *site.coords))
                        atom_prop_data = self._encode_atomic_properties(site.properties, num_atoms=1)
                        data.extend(atom_prop_data)
            else:
                lattice_data = structure.lattice_matrix.astype(np.float32).tobytes()
                data.extend(lattice_data)
                data.extend(struct.pack(BinaryFormat.UINT16, structure.spacegroup))
                
                if structure.storage_mode == StorageMode.SYMMETRIC:
                    data.extend(struct.pack(BinaryFormat.UINT8, len(structure.wyckoff_sites)))
                    for site in structure.wyckoff_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.UINT16, site.multiplicity))
                        data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                              *site.coords))
                        data.extend(struct.pack(BinaryFormat.FLOAT32, site.occupancy))
                else:
                    data.extend(struct.pack(BinaryFormat.UINT32, len(structure.atom_sites)))
                    for site in structure.atom_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                              *site.coords))
                        atom_prop_data = self._encode_atomic_properties(site.properties, num_atoms=1)
                        data.extend(atom_prop_data)
            
            struct_prop_data = self._encode_structure_properties(structure.structure_properties)
            data.extend(struct.pack(BinaryFormat.UINT32, len(struct_prop_data)))
            data.extend(struct_prop_data)
            
            formula_bytes = structure.formula.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT16, len(formula_bytes)))
            data.extend(formula_bytes)
            
            raw_data = bytes(data)
            compressed_data = self._compress_data(raw_data)
            
            header = bytearray(self.HEADER_SIZE)
            header[0:7] = b'USIF\x00\x00\x00'
            header[7:8] = struct.pack(BinaryFormat.UINT8, self.VERSION)
            header[8:12] = struct.pack(BinaryFormat.UINT32, len(raw_data))
            header[12:16] = struct.pack(BinaryFormat.UINT32, len(compressed_data))
            header[16:17] = struct.pack(BinaryFormat.UINT8, self.compression.value)
            
            hash_value = self._calculate_hash(structure)
            header[17:49] = hash_value
            
            return bytes(header) + compressed_data
            
        except Exception as e:
            if isinstance(e, (EncodingError, ValidationError)):
                raise
            raise EncodingError(f"Failed to encode structure: {e}") from e
    
    def decode(self, data: bytes) -> Tuple[USIFStructure, bytes]:
        """
        Decode bytes to USIFStructure
        
        Args:
            data: Encoded bytes
            
        Returns:
            Tuple of (USIFStructure, hash)
            
        Raises:
            DecodingError: If decoding fails
            CorruptedDataError: If data is corrupted
        """
        try:
            if len(data) < self.HEADER_SIZE:
                raise CorruptedDataError(f"Data too short: {len(data)} < {self.HEADER_SIZE}")
            
            magic = data[0:7]
            if magic != b'USIF\x00\x00\x00':
                raise CorruptedDataError(f"Invalid magic bytes: {magic}")
            
            version = struct.unpack(BinaryFormat.UINT8, data[7:8])[0]
            if version != self.VERSION:
                logger.warning(f"Version mismatch: file version {version}, expected {self.VERSION}")
            
            raw_size = struct.unpack(BinaryFormat.UINT32, data[8:12])[0]
            compressed_size = struct.unpack(BinaryFormat.UINT32, data[12:16])[0]
            comp_type = CompressionType(struct.unpack(BinaryFormat.UINT8, data[16:17])[0])
            hash_value = data[17:49]
            
            compressed_data = data[self.HEADER_SIZE:self.HEADER_SIZE + compressed_size]
            data = self._decompress_data(compressed_data, comp_type)
            
            offset = 0
            structure_type = StructureType(struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0])
            offset += 1
            storage_mode = StorageMode(struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0])
            offset += 1
            
            lattice_matrix = None
            spacegroup = 1
            point_group = None
            wyckoff_sites = None
            point_group_sites = None
            atom_sites = None
            
            if structure_type == StructureType.MOLECULAR:
                if storage_mode == StorageMode.SYMMETRIC:
                    pg_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                    offset += 1
                    point_group = data[offset:offset+pg_len].decode('utf-8')
                    offset += pg_len
                    
                    num_sites = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                    offset += 1
                    
                    point_group_sites = []
                    for _ in range(num_sites):
                        atomic_num = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                        mult = struct.unpack(BinaryFormat.UINT16, data[offset+1:offset+3])[0]
                        x, y, z_coord = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                                      data[offset+3:offset+15])
                        occupancy = struct.unpack(BinaryFormat.FLOAT32, data[offset+15:offset+19])[0]
                        offset += 19
                        point_group_sites.append(
                            PointGroupSite(atomic_num, mult, (x, y, z_coord), occupancy)
                        )
                else:
                    num_atoms = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                    offset += 4
                    
                    atom_sites = []
                    for _ in range(num_atoms):
                        atomic_num = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                        x, y, z_coord = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                                      data[offset+1:offset+13])
                        offset += 13
                        atom_props, offset = self._decode_atomic_properties(data, offset, num_atoms=1)
                        atom_sites.append(AtomSite(atomic_num, (x, y, z_coord), atom_props))
            else:
                lattice_data = data[offset:offset+36]
                lattice_matrix = np.frombuffer(lattice_data, dtype=np.float32).reshape(3, 3)
                offset += 36
                
                spacegroup = struct.unpack(BinaryFormat.UINT16, data[offset:offset+2])[0]
                offset += 2
                
                if storage_mode == StorageMode.SYMMETRIC:
                    num_sites = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                    offset += 1
                    
                    wyckoff_sites = []
                    for _ in range(num_sites):
                        atomic_num = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                        mult = struct.unpack(BinaryFormat.UINT16, data[offset+1:offset+3])[0]
                        x, y, z_coord = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                                      data[offset+3:offset+15])
                        occupancy = struct.unpack(BinaryFormat.FLOAT32, data[offset+15:offset+19])[0]
                        offset += 19
                        wyckoff_sites.append(
                            WyckoffSite(atomic_num, mult, (x, y, z_coord), occupancy)
                        )
                else:
                    num_atoms = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                    offset += 4
                    
                    atom_sites = []
                    for _ in range(num_atoms):
                        atomic_num = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                        x, y, z_coord = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                                      data[offset+1:offset+13])
                        offset += 13
                        atom_props, offset = self._decode_atomic_properties(data, offset, num_atoms=1)
                        atom_sites.append(AtomSite(atomic_num, (x, y, z_coord), atom_props))
            
            props_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
            offset += 4
            struct_props, offset = self._decode_structure_properties(data, offset)
            
            formula_len = struct.unpack(BinaryFormat.UINT16, data[offset:offset+2])[0]
            offset += 2
            formula = data[offset:offset+formula_len].decode('utf-8')
            
            if structure_type == StructureType.MOLECULAR:
                structure = USIFStructure(
                    structure_type=structure_type,
                    storage_mode=storage_mode,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    atom_sites=atom_sites,
                    structure_properties=struct_props,
                    formula=formula
                )
            else:
                structure = USIFStructure(
                    structure_type=structure_type,
                    lattice_matrix=lattice_matrix,
                    spacegroup=spacegroup,
                    storage_mode=storage_mode,
                    wyckoff_sites=wyckoff_sites,
                    atom_sites=atom_sites,
                    structure_properties=struct_props,
                    formula=formula
                )
            
            return structure, hash_value
            
        except (struct.error, UnicodeDecodeError) as e:
            raise DecodingError(f"Failed to decode data: {e}") from e
        except Exception as e:
            if isinstance(e, (DecodingError, CorruptedDataError, ValidationError)):
                raise
            raise DecodingError(f"Unexpected error during decoding: {e}") from e
    
    def get_structure_hash(self, structure: USIFStructure) -> str:
        """Get hexadecimal hash of structure"""
        return self._calculate_hash(structure).hex()
    
    def save(self, structure: USIFStructure, filename: Union[str, Path]) -> None:
        """Save structure to file"""
        try:
            with open(filename, 'wb') as f:
                f.write(self.encode(structure))
        except IOError as e:
            raise StorageError(f"Failed to save structure to {filename}: {e}") from e
    
    def load(self, filename: Union[str, Path]) -> USIFStructure:
        """Load structure from file"""
        try:
            with open(filename, 'rb') as f:
                structure, _ = self.decode(f.read())
            return structure
        except (IOError, FileNotFoundError) as e:
            raise StorageError(f"Failed to load structure from {filename}: {e}") from e


# ============================================================================
# Pymatgen Converter
# ============================================================================

class StructureConverter:
    """Conversion between USIF and pymatgen"""
    
    @staticmethod
    def from_pymatgen(pmg_obj: Union[PMGStructure, PMGMolecule],
                     forces: Optional[np.ndarray] = None,
                     stress: Optional[np.ndarray] = None,
                     energy: Optional[float] = None,
                     charges: Optional[np.ndarray] = None,
                     magmoms: Optional[np.ndarray] = None,
                     force_symmetric: bool = False,
                     **kwargs) -> USIFStructure:
        """
        Universal converter from pymatgen to USIF
        
        Args:
            pmg_obj: Pymatgen Structure or Molecule
            forces: Optional forces array
            stress: Optional stress tensor
            energy: Optional energy
            charges: Optional charges
            magmoms: Optional magnetic moments
            force_symmetric: Force symmetric storage
            
        Returns:
            USIFStructure instance
        """
        is_molecule = isinstance(pmg_obj, PMGMolecule)
        
        if is_molecule:
            return StructureConverter._from_molecule(
                pmg_obj, forces, charges, energy, force_symmetric, **kwargs
            )
        else:
            return StructureConverter._from_crystal(
                pmg_obj, forces, stress, energy, charges, magmoms, force_symmetric, **kwargs
            )
    
    @staticmethod
    def _from_molecule(pmg_molecule: PMGMolecule,
                      forces: Optional[np.ndarray] = None,
                      charges: Optional[np.ndarray] = None,
                      energy: Optional[float] = None,
                      force_symmetric: bool = False,
                      **kwargs) -> USIFStructure:
        """Convert pymatgen Molecule to USIF"""
        has_atomic_properties = forces is not None or charges is not None
        
        if force_symmetric or (not has_atomic_properties):
            try:
                pga = PointGroupAnalyzer(pmg_molecule)
                point_group = pga.sch_symbol
                
                atom_groups = defaultdict(list)
                
                for i, site in enumerate(pmg_molecule):
                    atomic_num = site.specie.Z
                    atom_groups[atomic_num].append((i, np.array(site.coords)))
                
                point_group_sites = []
                used = set()
                
                for atomic_num, atoms in atom_groups.items():
                    for idx, coords in atoms:
                        if idx in used:
                            continue
                        
                        equiv_count = 1
                        used.add(idx)
                        
                        for other_idx, other_coords in atoms:
                            if other_idx in used:
                                continue
                            
                            min_dist = float('inf')
                            for sym_op in pga.get_symmetry_operations():
                                transformed = sym_op.operate(coords)
                                dist = np.linalg.norm(transformed - other_coords)
                                min_dist = min(min_dist, dist)
                            
                            if min_dist < 0.01:
                                equiv_count += 1
                                used.add(other_idx)
                        
                        point_group_sites.append(
                            PointGroupSite(atomic_num, equiv_count, tuple(coords))
                        )
                
                total_multiplicity = sum(s.multiplicity for s in point_group_sites)
                if total_multiplicity == len(pmg_molecule) and \
                   len(point_group_sites) < len(pmg_molecule):
                    struct_props = StructureProperties()
                    if energy is not None:
                        struct_props.energy = energy
                    
                    formula = pmg_molecule.composition.reduced_formula
                    
                    return USIFStructure(
                        structure_type=StructureType.MOLECULAR,
                        storage_mode=StorageMode.SYMMETRIC,
                        point_group=point_group,
                        point_group_sites=point_group_sites,
                        structure_properties=struct_props,
                        formula=formula
                    )
            except Exception as e:
                logger.debug(f"Symmetric molecule conversion failed: {e}")
        
        atom_sites = []
        for i, site in enumerate(pmg_molecule):
            atomic_num = site.specie.Z
            
            atom_props = AtomicProperties()
            if forces is not None and i < len(forces):
                atom_props.force = tuple(forces[i])
            if charges is not None and i < len(charges):
                atom_props.charge = float(charges[i])
            
            atom_sites.append(AtomSite(atomic_num, tuple(site.coords), atom_props))
        
        struct_props = StructureProperties()
        if energy is not None:
            struct_props.energy = energy
        
        formula = pmg_molecule.composition.reduced_formula
        
        return USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=atom_sites,
            structure_properties=struct_props,
            formula=formula
        )
    
    @staticmethod
    def _from_crystal(pmg_structure: PMGStructure,
                     forces: Optional[np.ndarray] = None,
                     stress: Optional[np.ndarray] = None,
                     energy: Optional[float] = None,
                     charges: Optional[np.ndarray] = None,
                     magmoms: Optional[np.ndarray] = None,
                     force_symmetric: bool = False,
                     **kwargs) -> USIFStructure:
        """Convert pymatgen Structure to USIF"""
        lattice_matrix = pmg_structure.lattice.matrix.copy()
        
        has_atomic_properties = (
            forces is not None or charges is not None or magmoms is not None
        )
        
        if force_symmetric:
            storage_mode = StorageMode.SYMMETRIC
        else:
            storage_mode = StorageMode.FULL_ATOMIC if has_atomic_properties else StorageMode.SYMMETRIC
        
        wyckoff_sites = None
        atom_sites = None
        spacegroup_number = 1
        
        if storage_mode == StorageMode.SYMMETRIC:
            try:
                sga = SpacegroupAnalyzer(pmg_structure, symprec=0.1)
                spacegroup_number = sga.get_space_group_number()
                symmetrized = sga.get_symmetrized_structure()
                
                wyckoff_sites = []
                for equiv_sites in symmetrized.equivalent_sites:
                    rep = equiv_sites[0]
                    atomic_num = rep.specie.Z
                    wyckoff_sites.append(
                        WyckoffSite(atomic_num, len(equiv_sites), tuple(rep.frac_coords))
                    )
            except ValueError as e:
                logger.warning(f"Symmetry analysis failed, using full atomic: {e}")
                storage_mode = StorageMode.FULL_ATOMIC
            except RuntimeError as e:
                logger.error(f"Runtime error in symmetry analysis: {e}")
                storage_mode = StorageMode.FULL_ATOMIC
        
        if storage_mode == StorageMode.FULL_ATOMIC:
            try:
                sga = SpacegroupAnalyzer(pmg_structure, symprec=0.1)
                spacegroup_number = sga.get_space_group_number()
            except Exception as e:
                logger.warning(f"Failed to determine spacegroup: {e}")
                spacegroup_number = 1
            
            atom_sites = []
            for i, site in enumerate(pmg_structure):
                atomic_num = site.specie.Z
                
                atom_props = AtomicProperties()
                if forces is not None and i < len(forces):
                    atom_props.force = tuple(forces[i])
                if charges is not None and i < len(charges):
                    atom_props.charge = float(charges[i])
                if magmoms is not None and i < len(magmoms):
                    atom_props.magmom = float(magmoms[i])
                
                atom_sites.append(AtomSite(atomic_num, tuple(site.frac_coords), atom_props))
        
        struct_props = StructureProperties()
        
        if energy is not None:
            struct_props.energy = energy
        
        if stress is not None:
            if stress.shape == (3, 3):
                struct_props.stress = (
                    stress[0, 0], stress[1, 1], stress[2, 2],
                    stress[0, 1], stress[1, 2], stress[0, 2]
                )
            else:
                struct_props.stress = tuple(stress[:6])
        
        struct_props.volume = pmg_structure.volume
        
        formula = pmg_structure.composition.reduced_formula
        
        return USIFStructure(
            structure_type=StructureType.PERIODIC,
            lattice_matrix=lattice_matrix,
            spacegroup=spacegroup_number,
            storage_mode=storage_mode,
            wyckoff_sites=wyckoff_sites,
            atom_sites=atom_sites,
            structure_properties=struct_props,
            formula=formula
        )
    
    @staticmethod
    def to_pymatgen(usif_structure: USIFStructure) -> Union[PMGStructure, PMGMolecule]:
        """
        Convert USIF structure to pymatgen
        
        Args:
            usif_structure: USIF structure
            
        Returns:
            Pymatgen Structure or Molecule
        """
        if usif_structure.is_molecular():
            return StructureConverter._to_molecule(usif_structure)
        else:
            return StructureConverter._to_crystal(usif_structure)
    
    @staticmethod
    def _to_molecule(usif_structure: USIFStructure) -> PMGMolecule:
        """Convert USIF to pymatgen Molecule"""
        species = []
        coords = []
        site_properties = {}
        
        forces = []
        charges = []
        
        if usif_structure.storage_mode == StorageMode.SYMMETRIC:
            for site in usif_structure.point_group_sites:
                element = Element.from_Z(site.atomic_number)
                for _ in range(site.multiplicity):
                    species.append(element)
                    coords.append(site.coords)
        else:
            for atom in usif_structure.atom_sites:
                element = Element.from_Z(atom.atomic_number)
                species.append(element)
                coords.append(atom.coords)
                
                if atom.properties.force is not None:
                    forces.append(atom.properties.force)
                if atom.properties.charge is not None:
                    charges.append(atom.properties.charge)
        
        if forces:
            site_properties['forces'] = forces
        if charges:
            site_properties['charges'] = charges
        
        return PMGMolecule(species, coords, 
                          site_properties=site_properties if site_properties else None)
    
    @staticmethod
    def _to_crystal(usif_structure: USIFStructure) -> PMGStructure:
        """Convert USIF to pymatgen Structure"""
        lattice_matrix = usif_structure.lattice_matrix
        lattice = Lattice(lattice_matrix)
        
        species = []
        coords = []
        site_properties = {}
        
        if usif_structure.storage_mode == StorageMode.SYMMETRIC:
            for site in usif_structure.wyckoff_sites:
                element = Element.from_Z(site.atomic_number)
                for _ in range(site.multiplicity):
                    species.append(element)
                    coords.append(site.coords)
        else:
            forces = []
            charges = []
            magmoms = []
            
            for site in usif_structure.atom_sites:
                element = Element.from_Z(site.atomic_number)
                species.append(element)
                coords.append(site.coords)
                
                if site.properties.force is not None:
                    forces.append(site.properties.force)
                if site.properties.charge is not None:
                    charges.append(site.properties.charge)
                if site.properties.magmom is not None:
                    magmoms.append(site.properties.magmom)
            
            if forces:
                site_properties['forces'] = forces
            if charges:
                site_properties['charges'] = charges
            if magmoms:
                site_properties['magmoms'] = magmoms
        
        return PMGStructure(
            lattice, species, coords, coords_are_cartesian=False,
            site_properties=site_properties if site_properties else None
        )


# ============================================================================
# Container System with Thread Safety
# ============================================================================

@dataclass
class USIFGroup:
    """Group for organizing structures"""
    name: str
    structures: Dict[str, str] = field(default_factory=dict)
    subgroups: Dict[str, 'USIFGroup'] = field(default_factory=dict)
    
    def add_structure(self, name: str, struct_hash: str) -> None:
        """Add structure to group"""
        self.structures[name] = struct_hash
    
    def get_subgroup(self, path: str) -> Optional['USIFGroup']:
        """Get subgroup by path"""
        if not path or path == "/":
            return self
        
        parts = [p for p in path.split('/') if p]
        current = self
        
        for part in parts:
            if part in current.subgroups:
                current = current.subgroups[part]
            else:
                return None
        
        return current


class StructureContainer:
    """
    Container for storing multiple USIF structures with indexing
    Thread-safe implementation with proper error handling
    """
    
    CONTAINER_MAGIC = b'USIFC\x00\x00'
    CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB chunks
    
    def __init__(self, 
                 filename: Union[str, Path],
                 mode: str = "r",
                 compression: CompressionType = CompressionType.GZIP,
                 use_mmap: bool = True,
                 cache_size: int = 1000,
                 num_workers: int = 4):
        """
        Initialize container
        
        Args:
            filename: Container file path
            mode: Open mode ('r', 'w', 'a')
            compression: Compression type
            use_mmap: Use memory mapping
            cache_size: Cache size
            num_workers: Number of worker threads
        """
        if mode not in ('r', 'w', 'a'):
            raise ValueError(f"Invalid mode: {mode}. Must be 'r', 'w', or 'a'")
        
        self.filename = Path(filename).resolve()
        self.mode = mode
        self.encoder = USIF(compression=compression)
        self.use_mmap = use_mmap
        self.num_workers = max(1, min(num_workers, 32))
        
        # Thread-safe cache
        self._cache = OrderedDict()
        self._cache_lock = threading.RLock()
        self._cache_size = cache_size
        
        # Indexes
        self._hash_index: Dict[str, Tuple[int, int, int]] = {}
        self._name_index: Dict[str, str] = {}
        self._formula_index: Dict[str, List[str]] = defaultdict(list)
        self._property_index: Dict[str, Dict[Any, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._group_index: Dict[str, USIFGroup] = {}
        
        # File and mmap
        self._file = None
        self._mmap = None
        
        # Group hierarchy
        self.root_group = USIFGroup("/")
        
        # Prefetch queue
        self._prefetch_queue = queue.Queue()
        self._prefetch_thread = None
        
        # Data offsets
        self._data_offset = self.HEADER_SIZE = 64
        self._index_offset = 0
        
        # Initialize
        if mode == "r":
            if not self.filename.exists():
                raise FileNotFoundError(f"File not found: {self.filename}")
            self._file = open(self.filename, "rb")
            if use_mmap:
                try:
                    self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
                except Exception as e:
                    logger.warning(f"Failed to create mmap: {e}")
                    self.use_mmap = False
            self._read_enhanced_index()
        elif mode in ["w", "a"]:
            if mode == "a" and self.filename.exists():
                self._file = open(self.filename, "r+b")
                if use_mmap:
                    try:
                        self._mmap = mmap.mmap(self._file.fileno(), 0)
                    except Exception as e:
                        logger.warning(f"Failed to create mmap: {e}")
                        self.use_mmap = False
                self._read_enhanced_index()
            else:
                # Use w+b to allow both writing and reading
                # Don't use mmap for new files (file is initially empty)
                self._file = open(self.filename, "w+b")
                self.use_mmap = False  # Disable mmap for new write mode
                self._write_header()
        
        # Start prefetch thread
        if self._prefetch_queue and num_workers > 0:
            self._start_prefetch_thread()
    
    def _write_header(self) -> None:
        """Write container header"""
        header = bytearray(self.HEADER_SIZE)
        header[0:7] = self.CONTAINER_MAGIC
        header[7:8] = struct.pack(BinaryFormat.UINT8, 1)  # Version
        header[8:12] = struct.pack(BinaryFormat.UINT32, 0)  # num_structures
        header[12:20] = struct.pack(BinaryFormat.UINT64, self.HEADER_SIZE)  # data_offset
        header[20:28] = struct.pack(BinaryFormat.UINT64, 0)  # index_offset
        header[28:36] = struct.pack(BinaryFormat.UINT64, 0)  # group_offset
        header[36:44] = struct.pack(BinaryFormat.UINT64, 0)  # attribute_offset
        header[44:45] = struct.pack(BinaryFormat.UINT8, self.encoder.compression.value)
        header[45:46] = struct.pack(BinaryFormat.UINT8, 1)  # use_chunking
        
        import time
        timestamp = int(time.time())
        header[46:54] = struct.pack(BinaryFormat.UINT64, timestamp)
        header[54:62] = struct.pack(BinaryFormat.UINT64, timestamp)
        
        self._file.write(header)
        self._file.flush()
    
    def _read_enhanced_index(self) -> None:
        """Read enhanced index with secondary indexes"""
        try:
            if self._mmap:
                data = self._mmap
            else:
                self._file.seek(0)
                data = self._file.read()
            
            magic = data[0:7]
            if magic != self.CONTAINER_MAGIC:
                raise CorruptedDataError("Invalid enhanced USIF container")
            
            version = struct.unpack(BinaryFormat.UINT8, data[7:8])[0]
            num_structures = struct.unpack(BinaryFormat.UINT32, data[8:12])[0]
            data_offset = struct.unpack(BinaryFormat.UINT64, data[12:20])[0]
            index_offset = struct.unpack(BinaryFormat.UINT64, data[20:28])[0]
            group_offset = struct.unpack(BinaryFormat.UINT64, data[28:36])[0]
            
            self._data_offset = data_offset
            self._index_offset = index_offset
            
            if index_offset > 0:
                self._file.seek(index_offset)
                for _ in range(num_structures):
                    hash_bytes = self._file.read(32)
                    chunk_id = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
                    chunk_offset = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
                    size = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
                    self._hash_index[hash_bytes.hex()] = (chunk_id, chunk_offset, size)
            
            if group_offset > 0:
                self._read_group_hierarchy(group_offset)
            
            self._build_secondary_indexes()
            
        except Exception as e:
            logger.error(f"Failed to read index: {e}")
            raise StorageError(f"Failed to read container index: {e}") from e
    
    def _read_group_hierarchy(self, group_offset: int) -> None:
        """Read group hierarchy from file"""
        try:
            self._file.seek(group_offset)
            
            num_groups = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
            
            for _ in range(num_groups):
                name_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
                name = self._file.read(name_len).decode('utf-8')
                
                num_structures = struct.unpack(BinaryFormat.UINT32, self._file.read(4))[0]
                group = self.create_group(name)
                
                for _ in range(num_structures):
                    struct_name_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
                    struct_name = self._file.read(struct_name_len).decode('utf-8')
                    hash_len = struct.unpack(BinaryFormat.UINT16, self._file.read(2))[0]
                    struct_hash = self._file.read(hash_len).decode('utf-8')
                    
                    group.add_structure(struct_name, struct_hash)
                    self._name_index[struct_name] = struct_hash
        except Exception as e:
            logger.error(f"Failed to read group hierarchy: {e}")
    
    def _build_secondary_indexes(self) -> None:
        """Build secondary indexes for fast querying"""
        logger.info("Building secondary indexes...")
        
        for struct_hash in list(self._hash_index.keys())[:10]:
            try:
                structure = self.get(struct_hash)
                if structure:
                    self._formula_index[structure.formula].append(struct_hash)
                    
                    props = structure.structure_properties.get_all_properties()
                    for prop_name, value in props.items():
                        if isinstance(value, (int, float)):
                            bucket = round(value, 3)
                            self._property_index[prop_name][bucket].append(struct_hash)
                        else:
                            self._property_index[prop_name][value].append(struct_hash)
            except Exception as e:
                logger.warning(f"Failed to index structure {struct_hash[:16]}: {e}")
    
    def _start_prefetch_thread(self) -> None:
        """Start background thread for prefetching"""
        def prefetch_worker():
            while True:
                try:
                    hashes = self._prefetch_queue.get(timeout=1.0)
                    if hashes is None:
                        break
                    for h in hashes:
                        with self._cache_lock:
                            if h not in self._cache:
                                self.get(h)
                    self._prefetch_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Prefetch error: {e}")
        
        self._prefetch_thread = threading.Thread(target=prefetch_worker, daemon=True)
        self._prefetch_thread.start()
    
    def add(self, structure: USIFStructure, name: Optional[str] = None, 
            group: str = "/") -> str:
        """
        Add structure with optional naming and grouping
        
        Args:
            structure: USIF structure to add
            name: Optional name for the structure
            group: Group path (default is root)
            
        Returns:
            Structure hash
            
        Raises:
            ValueError: If container is read-only
            ValidationError: If input is invalid
        """
        if self.mode == 'r':
            raise ValueError("Cannot add to read-only container")
        
        if not isinstance(structure, USIFStructure):
            raise ValidationError(f"Expected USIFStructure, got {type(structure).__name__}")
        
        try:
            usif_data = self.encoder.encode(structure)
            struct_hash = self.encoder.get_structure_hash(structure)
            
            if struct_hash in self._hash_index:
                logger.info(f"Structure {struct_hash[:16]} already exists")
                return struct_hash
            
            chunk_id, chunk_offset = self._allocate_space(len(usif_data))
            self._write_to_chunk(chunk_id, chunk_offset, usif_data)
            
            self._hash_index[struct_hash] = (chunk_id, chunk_offset, len(usif_data))
            
            if name:
                self._name_index[name] = struct_hash
            
            target_group = self._get_or_create_group(group)
            display_name = name or struct_hash[:16]
            target_group.add_structure(display_name, struct_hash)
            
            self._update_secondary_indexes(structure, struct_hash)
            
            logger.debug(f"Added structure {struct_hash[:16]} (name: {name or 'N/A'})")
            
            return struct_hash
            
        except Exception as e:
            logger.error(f"Failed to add structure: {e}")
            raise StorageError(f"Failed to add structure: {e}") from e
    
    def _allocate_space(self, size: int) -> Tuple[int, int]:
        """Allocate space in chunked storage"""
        if self._mmap:
            current_pos = self._mmap.size()
        else:
            self._file.seek(0, 2)  # Seek to end
            current_pos = self._file.tell()
        
        chunk_id = current_pos // self.CHUNK_SIZE
        chunk_offset = current_pos % self.CHUNK_SIZE
        
        if chunk_offset + size > self.CHUNK_SIZE:
            chunk_id += 1
            chunk_offset = 0
            if self._mmap:
                self._mmap.resize(chunk_id * self.CHUNK_SIZE)
            else:
                # Pad to the start of next chunk
                padding_size = self.CHUNK_SIZE - (current_pos % self.CHUNK_SIZE)
                if padding_size > 0:
                    self._file.write(b'\x00' * padding_size)
                    self._file.flush()
        
        return chunk_id, chunk_offset
    
    def _write_to_chunk(self, chunk_id: int, offset: int, data: bytes) -> None:
        """Write data to specific chunk"""
        actual_offset = chunk_id * self.CHUNK_SIZE + offset
        
        if self._mmap:
            required_size = actual_offset + len(data)
            if required_size > self._mmap.size():
                self._mmap.resize(required_size)
            self._mmap[actual_offset:actual_offset + len(data)] = data
            self._mmap.flush()  # Ensure data is written
        else:
            # Get current file size
            current_pos = self._file.tell()
            self._file.seek(0, 2)
            file_size = self._file.tell()
            
            # If we need to write beyond current file size, extend the file
            required_size = actual_offset + len(data)
            if required_size > file_size:
                # Pad with zeros if there's a gap
                if actual_offset > file_size:
                    self._file.write(b'\x00' * (actual_offset - file_size))
            
            # Write the data
            self._file.seek(actual_offset)
            self._file.write(data)
            self._file.flush()  # Ensure data is flushed to disk
    
    def _get_or_create_group(self, path: str) -> USIFGroup:
        """Get or create group by path"""
        if path == "/":
            return self.root_group
        
        parts = [p for p in path.split('/') if p]
        current = self.root_group
        
        full_path = "/"
        for part in parts:
            full_path += part + "/"
            if part not in current.subgroups:
                current.subgroups[part] = USIFGroup(part)
                self._group_index[full_path] = current.subgroups[part]
            current = current.subgroups[part]
        
        return current
    
    def _update_secondary_indexes(self, structure: USIFStructure, struct_hash: str) -> None:
        """Update secondary indexes for a structure"""
        self._formula_index[structure.formula].append(struct_hash)
        
        props = structure.structure_properties.get_all_properties()
        for prop_name, value in props.items():
            if isinstance(value, (int, float)):
                bucket = round(value, 3)
                self._property_index[prop_name][bucket].append(struct_hash)
            else:
                self._property_index[prop_name][value].append(struct_hash)
    
    def get(self, identifier: str) -> Optional[USIFStructure]:
        """
        Get structure by hash or name (thread-safe)
        
        Args:
            identifier: Structure hash or name
            
        Returns:
            USIF structure or None if not found
        """
        with self._cache_lock:
            if identifier in self._cache:
                self._cache.move_to_end(identifier)
                return self._cache[identifier]
        
        struct_hash = self._name_index.get(identifier, identifier)
        
        if struct_hash not in self._hash_index:
            return None
        
        chunk_id, chunk_offset, size = self._hash_index[struct_hash]
        usif_data = self._read_from_chunk(chunk_id, chunk_offset, size)
        
        try:
            structure, _ = self.encoder.decode(usif_data)
            
            with self._cache_lock:
                self._cache[identifier] = structure
                if len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            
            return structure
            
        except Exception as e:
            logger.error(f"Error decoding structure {identifier}: {e}")
            return None
    
    def _read_from_chunk(self, chunk_id: int, offset: int, size: int) -> bytes:
        """Read data from specific chunk"""
        actual_offset = chunk_id * self.CHUNK_SIZE + offset
        
        if self._mmap:
            return bytes(self._mmap[actual_offset:actual_offset + size])
        else:
            current_pos = self._file.tell()
            self._file.seek(actual_offset)
            data = self._file.read(size)
            self._file.seek(current_pos)
            return data
    
    def query(self, 
              formula: Optional[str] = None,
              properties: Optional[Dict[str, Any]] = None,
              energy_range: Optional[Tuple[float, float]] = None,
              group: Optional[str] = None) -> List[Tuple[str, USIFStructure]]:
        """
        Enhanced query with multiple criteria
        
        Args:
            formula: Chemical formula
            properties: Property filters
            energy_range: Energy range (min, max)
            group: Group path
            
        Returns:
            List of (hash, structure) tuples
        """
        results = []
        
        candidate_hashes = set()
        if formula:
            candidate_hashes.update(self._formula_index.get(formula, []))
        else:
            candidate_hashes.update(self._hash_index.keys())
        
        if properties:
            for prop_name, prop_value in properties.items():
                if prop_name in self._property_index:
                    if isinstance(prop_value, (int, float)):
                        for bucket, hashes in self._property_index[prop_name].items():
                            if isinstance(bucket, (int, float)) and abs(bucket - prop_value) < 0.001:
                                candidate_hashes.intersection_update(hashes)
                    else:
                        if prop_value in self._property_index[prop_name]:
                            candidate_hashes.intersection_update(
                                self._property_index[prop_name][prop_value]
                            )
        
        if energy_range:
            min_energy, max_energy = energy_range
            energy_hashes = set()
            for bucket, hashes in self._property_index.get('energy', {}).items():
                if isinstance(bucket, (int, float)) and min_energy <= bucket <= max_energy:
                    energy_hashes.update(hashes)
            candidate_hashes.intersection_update(energy_hashes)
        
        if group and group != "/":
            group_hashes = set()
            target_group = self.get_group(group)
            if target_group:
                for struct_name, struct_hash in target_group.structures.items():
                    group_hashes.add(struct_hash)
            candidate_hashes.intersection_update(group_hashes)
        
        for hash_val in candidate_hashes:
            structure = self.get(hash_val)
            if structure:
                results.append((hash_val, structure))
        
        return results
    
    def get_group(self, path: str) -> Optional[USIFGroup]:
        """Get group by path"""
        return self.root_group.get_subgroup(path)
    
    def create_group(self, path: str) -> USIFGroup:
        """Create group hierarchy"""
        return self._get_or_create_group(path)
    
    def prefetch(self, identifiers: List[str]) -> None:
        """Prefetch structures for faster access"""
        if self._prefetch_queue:
            self._prefetch_queue.put(identifiers)
    
    def get_batch_parallel(self, identifiers: List[str]) -> List[Optional[USIFStructure]]:
        """
        Batch read using multiple threads (optimized)
        
        Args:
            identifiers: List of structure identifiers
            
        Returns:
            List of structures in same order as identifiers
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if not identifiers:
            return []
        
        ident_to_idx = {ident: idx for idx, ident in enumerate(identifiers)}
        results = [None] * len(identifiers)
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_ident = {
                executor.submit(self.get, ident): ident 
                for ident in identifiers
            }
            
            for future in as_completed(future_to_ident):
                ident = future_to_ident[future]
                idx = ident_to_idx[ident]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Failed to get structure {ident}: {e}")
                    results[idx] = None
        
        return results
    
    def _write_enhanced_index(self) -> None:
        """Write enhanced index to file"""
        if self.mode == 'r':
            return
    
    def _serialize_group_hierarchy(self) -> bytes:
        """Serialize group hierarchy to bytes"""
        return b''
    
    def stats(self) -> Dict[str, Any]:
        """Get detailed container statistics"""
        total_structures = len(self._hash_index)
        total_groups = len(self._group_index)
        
        total_size = sum(size for _, _, size in self._hash_index.values())
        avg_size = total_size / total_structures if total_structures else 0
        
        hash_index_size = total_structures * 44
        secondary_index_size = sum(
            len(hashes) * 16 for hashes in self._formula_index.values()
        ) + sum(
            len(bucket_hashes) * 16 for prop_dict in self._property_index.values()
            for bucket_hashes in prop_dict.values()
        )
        
        with self._cache_lock:
            cache_size = len(self._cache)
        
        return {
            'total_structures': total_structures,
            'total_groups': total_groups,
            'total_size_bytes': total_size,
            'average_structure_size': avg_size,
            'hash_index_size': hash_index_size,
            'secondary_index_size': secondary_index_size,
            'cache_size': cache_size,
            'cache_hit_ratio': 0.0,
            'compression_enabled': self.encoder.compression != CompressionType.NONE,
            'mmap_enabled': self.use_mmap,
            'chunk_size': self.CHUNK_SIZE,
        }
    
    def close(self) -> None:
        """Close container and cleanup"""
        if hasattr(self, '_prefetch_thread') and self._prefetch_thread and \
           self._prefetch_thread.is_alive():
            self._prefetch_queue.put(None)
            self._prefetch_thread.join(timeout=5.0)
        
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        
        if self._file:
            self._file.close()
            self._file = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __len__(self):
        return len(self._hash_index)
    
    def __contains__(self, identifier: str):
        return identifier in self._hash_index or identifier in self._name_index
    
    def __iter__(self):
        for struct_hash in self._hash_index:
            structure = self.get(struct_hash)
            if structure:
                yield struct_hash, structure
    
    def list_groups(self) -> List[str]:
        """List all groups in container"""
        return list(self._group_index.keys())
    
    def get_structures_in_group(self, group_path: str) -> List[Tuple[str, USIFStructure]]:
        """Get all structures in a specific group"""
        group = self.get_group(group_path)
        if not group:
            return []
        
        results = []
        for name, struct_hash in group.structures.items():
            structure = self.get(struct_hash)
            if structure:
                results.append((name, structure))
        
        return results


# ============================================================================
# Performance Optimizations and Utilities
# ============================================================================

class USIFOptimizer:
    """Performance optimization utilities for USIF"""
    
    @staticmethod
    def optimize_structure(structure: USIFStructure, 
                          tolerance: float = 1e-3) -> USIFStructure:
        """
        Optimize structure for maximum compression
        
        Args:
            structure: Input USIF structure
            tolerance: Symmetry tolerance for grouping
            
        Returns:
            Optimized USIF structure
        """
        if structure.is_periodic():
            return USIFOptimizer._optimize_crystal(structure, tolerance)
        else:
            return USIFOptimizer._optimize_molecule(structure, tolerance)
    
    @staticmethod
    def _optimize_crystal(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize crystal structure"""
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure
        
        try:
            pmg_structure = StructureConverter.to_pymatgen(structure)
            
            sga = SpacegroupAnalyzer(pmg_structure, symprec=tolerance)
            symmetrized = sga.get_symmetrized_structure()
            
            wyckoff_sites = []
            for equiv_sites in symmetrized.equivalent_sites:
                rep = equiv_sites[0]
                atomic_num = rep.specie.Z
                wyckoff_sites.append(
                    WyckoffSite(atomic_num, len(equiv_sites), tuple(rep.frac_coords))
                )
            
            return USIFStructure(
                structure_type=StructureType.PERIODIC,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=structure.lattice_matrix,
                spacegroup=sga.get_space_group_number(),
                wyckoff_sites=wyckoff_sites,
                structure_properties=structure.structure_properties,
                formula=structure.formula
            )
        except Exception as e:
            logger.debug(f"Crystal optimization failed: {e}")
            return structure
    
    @staticmethod
    def _optimize_molecule(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize molecular structure"""
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure
        
        try:
            pmg_molecule = StructureConverter.to_pymatgen(structure)
            
            pga = PointGroupAnalyzer(pmg_molecule)
            point_group = pga.sch_symbol
            
            atom_groups = defaultdict(list)
            
            for i, site in enumerate(pmg_molecule):
                atomic_num = site.specie.Z
                atom_groups[atomic_num].append((i, np.array(site.coords)))
            
            point_group_sites = []
            used = set()
            
            for atomic_num, atoms in atom_groups.items():
                for idx, coords in atoms:
                    if idx in used:
                        continue
                    
                    equiv_count = 1
                    used.add(idx)
                    
                    for other_idx, other_coords in atoms:
                        if other_idx in used:
                            continue
                        
                        min_dist = float('inf')
                        for sym_op in pga.get_symmetry_operations():
                            transformed = sym_op.operate(coords)
                            dist = np.linalg.norm(transformed - other_coords)
                            min_dist = min(min_dist, dist)
                        
                        if min_dist < tolerance:
                            equiv_count += 1
                            used.add(other_idx)
                    
                    point_group_sites.append(
                        PointGroupSite(atomic_num, equiv_count, tuple(coords))
                    )
            
            total_multiplicity = sum(s.multiplicity for s in point_group_sites)
            if total_multiplicity == len(pmg_molecule) and \
               len(point_group_sites) < len(pmg_molecule):
                return USIFStructure(
                    structure_type=StructureType.MOLECULAR,
                    storage_mode=StorageMode.SYMMETRIC,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    structure_properties=structure.structure_properties,
                    formula=structure.formula
                )
        except Exception as e:
            logger.debug(f"Molecule optimization failed: {e}")
        
        return structure


class USIFBenchmark:
    """Benchmarking utilities for USIF performance"""
    
    @staticmethod
    def benchmark_compression(structures: List[USIFStructure]) -> Dict[str, Any]:
        """
        Benchmark compression performance
        
        Args:
            structures: List of structures to benchmark
            
        Returns:
            Dictionary with benchmark results
        """
        encoder = USIF()
        
        total_original_size = 0
        total_compressed_size = 0
        compression_times = []
        decompression_times = []
        
        import time
        
        for structure in structures:
            try:
                start = time.time()
                compressed = encoder.encode(structure)
                compression_times.append(time.time() - start)
                
                start = time.time()
                decoded, _ = encoder.decode(compressed)
                decompression_times.append(time.time() - start)
                
                pmg_structure = StructureConverter.to_pymatgen(structure)
                cif_size = len(pmg_structure.to(fmt="cif"))
                total_original_size += cif_size
                total_compressed_size += len(compressed)
            except Exception as e:
                logger.error(f"Benchmark error for structure: {e}")
                continue
        
        avg_compression_ratio = total_compressed_size / total_original_size \
                               if total_original_size > 0 else 0
        avg_compression_time = np.mean(compression_times) if compression_times else 0
        avg_decompression_time = np.mean(decompression_times) if decompression_times else 0
        
        return {
            'num_structures': len(structures),
            'total_original_size': total_original_size,
            'total_compressed_size': total_compressed_size,
            'average_compression_ratio': avg_compression_ratio,
            'average_compression_time': avg_compression_time,
            'average_decompression_time': avg_decompression_time,
            'compression_speedup': 1.0 / avg_compression_ratio if avg_compression_ratio > 0 else 0
        }


# ============================================================================
# Main Usage Examples
# ============================================================================

def main():
    """Main demonstration function"""
    print("USIF (Universal Structure Interchange Format) Demo")
    print("=" * 50)
    
    try:
        # Create a simple crystal structure
        lattice = np.array([
            [5.0, 0.0, 0.0],
            [0.0, 5.0, 0.0],
            [0.0, 0.0, 5.0]
        ])
        
        wyckoff_sites = [
            WyckoffSite(14, 8, (0.0, 0.0, 0.0)),  # Silicon
            WyckoffSite(8, 16, (0.25, 0.25, 0.25))  # Oxygen
        ]
        
        crystal_structure = USIFStructure(
            structure_type=StructureType.PERIODIC,
            storage_mode=StorageMode.SYMMETRIC,
            lattice_matrix=lattice,
            spacegroup=227,
            wyckoff_sites=wyckoff_sites,
            formula="SiO2"
        )
        
        # Create encoder
        encoder = USIF()
        
        # Encode structure
        encoded_data = encoder.encode(crystal_structure)
        structure_hash = encoder.get_structure_hash(crystal_structure)
        
        print(f"Crystal structure: {crystal_structure.formula}")
        print(f"Number of atoms: {crystal_structure.num_atoms()}")
        print(f"Encoded size: {len(encoded_data)} bytes")
        print(f"Structure hash: {structure_hash}")
        
        # Decode structure
        decoded_structure, _ = encoder.decode(encoded_data)
        print(f"Decoded successfully: {crystal_structure == decoded_structure}")
        
        # Test container
        with StructureContainer("test_container.usifc", mode="w") as container:
            container.add(crystal_structure, name="silica_crystal", group="/crystals")
            
            # Query container
            results = container.query(formula="SiO2")
            print(f"Found {len(results)} structures with formula SiO2")
        
        print("Demo completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"Demo failed: {e}")


if __name__ == "__main__":
    main()
