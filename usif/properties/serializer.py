#!/usr/bin/env python3
"""
USIF Property Serializer
Serialize and deserialize property values
"""

import struct
import numpy as np
from typing import Any, Optional, Tuple

from usif.constants import BinaryFormat
from usif.exceptions import EncodingError, DecodingError
from usif.properties.definitions import PropertyDefinition

class PropertySerializer:
    """Serialize and deserialize property values with clear structure vs atomic distinction"""
    
    # Constants for efficient count encoding
    SINGLE_VALUE_FLAG = 0  # Indicates single value repeated for all atoms
    LONG_COUNT_FLAG = 255  # Indicates 4-byte count follows
    
    # Type handlers for serialization
    # Both atomic and structure-level properties can be scalar (no dimensions) or multi-dimensional (with dimensions)
    # - single_value_format: Format for serializing a single scalar value (higher precision, e.g., FLOAT64)
    # - element_format: Format for serializing each element in a multi-dimensional value (space-efficient, e.g., FLOAT32)
    # - single_value_size: Size in bytes for a single scalar value
    # - element_size: Size in bytes for each element in a multi-dimensional value
    TYPE_HANDLERS = {
        float: {
            'single_value_format': BinaryFormat.FLOAT64,  # Higher precision for single values
            'element_format': BinaryFormat.FLOAT32,       # Space-efficient for array elements
            'single_value_size': 8,
            'element_size': 4
        },
        int: {
            'single_value_format': BinaryFormat.INT64,    # Higher precision for single values
            'element_format': BinaryFormat.INT32,         # Space-efficient for array elements
            'single_value_size': 8,
            'element_size': 4
        },
        bool: {
            'single_value_format': BinaryFormat.BOOL,
            'element_format': BinaryFormat.BOOL,
            'single_value_size': 1,
            'element_size': 1
        },
        str: {
            'single_value_format': None,  # Strings use custom encoding
            'element_format': None,       # Strings use custom encoding
            'single_value_size': lambda x: PropertySerializer._get_string_size(x),
            'element_size': lambda x: PropertySerializer._get_string_size(x)
        },
        tuple: {
            'single_value_format': None,  # Tuples are always multi-dimensional
            'element_format': BinaryFormat.FLOAT32,  # Format for each element in tuple
            'single_value_size': lambda dim: dim * 4,
            'element_size': lambda dim: dim * 4
        }
    }
    
    @staticmethod
    def _get_string_size(value: str) -> int:
        """Calculate encoded string size"""
        if not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value)}")
        encoded_len = len(value.encode('utf-8'))
        return 1 + encoded_len if encoded_len <= 255 else 5 + encoded_len
    
    @staticmethod
    def _is_sequence(value: Any) -> bool:
        """Check if value is a sequence (but not string or bytes)"""
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
        """Serialize property value to bytes - unified handling for scalars and arrays"""
        if value is None:
            return b''
        
        try:
            # Unified approach: check if it's atomic or structure-level
            if prop_def.is_per_atom:
                # Atomic property: can be scalar or array, needs count encoding
                return PropertySerializer._serialize_atom_property(value, prop_def, num_atoms)
            else:
                # Structure-level property: can be scalar or array, no count needed
                return PropertySerializer._serialize_structure_property(value, prop_def)
        except (struct.error, UnicodeEncodeError, ValueError, TypeError) as e:
            raise EncodingError(f"Failed to serialize property '{prop_def.name}': {e}") from e
        except Exception as e:
            raise EncodingError(f"Unexpected error serializing property '{prop_def.name}': {e}") from e
    
    @staticmethod
    def _serialize_atom_property(value: Any, prop_def: PropertyDefinition,
                                 num_atoms: Optional[int] = None) -> bytes:
        """Serialize atomic property - unified handling for scalars and arrays"""
        data = bytearray()
        
        # Check if this is a single multi-dimensional element (like one force vector)
        is_multi_dim = PropertySerializer._is_multi_dimensional_element(value) and prop_def.dimensions
        is_sequence = PropertySerializer._is_sequence(value) and not is_multi_dim
        
        if is_sequence:
            # Multiple values (list/array of values)
            actual_count = len(value)
            if actual_count == 0:
                raise EncodingError("Cannot serialize empty sequence for atomic property")
            
            # Validate count: must be 1 (single value repeated) or num_atoms (one per atom)
            if num_atoms is not None and actual_count != 1 and actual_count != num_atoms:
                raise EncodingError(
                    f"Atomic property count mismatch: expected 1 or {num_atoms}, got {actual_count}"
                )
            
            # Encode count
            if actual_count <= PropertySerializer.LONG_COUNT_FLAG - 1:
                data.extend(struct.pack(BinaryFormat.UINT8, actual_count))
            else:
                data.extend(struct.pack(BinaryFormat.UINT8, PropertySerializer.LONG_COUNT_FLAG))
                data.extend(struct.pack(BinaryFormat.UINT32, actual_count))
            
            # Serialize each value
            for atom_value in value:
                element_data = PropertySerializer._serialize_element(atom_value, prop_def)
                data.extend(element_data)
        else:
            # Single value (scalar or multi-dimensional element) - use special flag
            data.extend(struct.pack(BinaryFormat.UINT8, PropertySerializer.SINGLE_VALUE_FLAG))
            element_data = PropertySerializer._serialize_element(value, prop_def)
            data.extend(element_data)
        
        return bytes(data)
    
    @staticmethod
    def _serialize_structure_property(value: Any, prop_def: PropertyDefinition) -> bytes:
        """Serialize structure-level property - unified handling for scalars and arrays"""
        # Structure properties don't need count encoding, just serialize the value directly
        return PropertySerializer._serialize_element(value, prop_def)
    
    @staticmethod
    def _serialize_element(value: Any, prop_def: PropertyDefinition) -> bytes:
        """Serialize a single element - unified handling for scalars and multi-dimensional values"""
        if prop_def.dimensions:
            # Multi-dimensional element (e.g., force vector, stress tensor)
            return PropertySerializer._serialize_multi_dimensional(value, prop_def)
        else:
            # Scalar element
            return PropertySerializer._serialize_scalar_value(value, prop_def)
    
    @staticmethod
    def _serialize_multi_dimensional(value: Any, prop_def: PropertyDefinition) -> bytes:
        """Serialize multi-dimensional array element"""
        dim = prop_def.dimensions[0]
        
        # Validate that value is a sequence with correct length
        if not PropertySerializer._is_sequence(value):
            raise EncodingError(
                f"Expected sequence for multi-dimensional property, got {type(value).__name__}"
            )
        
        if len(value) != dim:
            raise EncodingError(
                f"Dimension mismatch: expected {dim} elements, got {len(value)}"
            )
        
        # Validate that all elements are numeric
        if not all(isinstance(x, (int, float)) for x in value):
            raise EncodingError(
                f"All elements must be numeric (int or float), got mixed types"
            )
        
        # Serialize based on data type
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
    def _serialize_scalar_value(value: Any, prop_def: PropertyDefinition) -> bytes:
        """Serialize scalar value (used for both structure and atomic properties)"""
        handler = PropertySerializer.TYPE_HANDLERS.get(prop_def.data_type)
        if not handler:
            raise EncodingError(f"Unsupported scalar type: {prop_def.data_type}")
        
        if prop_def.data_type == str:
            if not isinstance(value, str):
                raise EncodingError(f"Expected string, got {type(value).__name__}")
            return PropertySerializer._serialize_string(value)
        
        # For scalar values, prefer element_format (space-efficient) when available,
        # fallback to single_value_format (higher precision)
        fmt = handler.get('element_format') or handler.get('single_value_format')
        if fmt:
            try:
                return struct.pack(fmt, value)
            except struct.error as e:
                raise EncodingError(f"Failed to pack value {value} with format {fmt}: {e}") from e
        raise EncodingError(f"Format not defined for {prop_def.data_type}")
    
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
        """Deserialize property value from bytes - unified handling for scalars and arrays"""
        if len(data) <= offset:
            return None, offset
        
        try:
            # Unified approach: check if it's atomic or structure-level
            if prop_def.is_per_atom:
                # Atomic property: needs count decoding
                return PropertySerializer._deserialize_atom_property(data, offset, prop_def, num_atoms)
            else:
                # Structure-level property: no count, just deserialize the value
                return PropertySerializer._deserialize_structure_property(data, offset, prop_def)
        except (struct.error, UnicodeDecodeError, ValueError, IndexError) as e:
            raise DecodingError(
                f"Failed to deserialize property '{prop_def.name}' at offset {offset}: {e}"
            ) from e
        except Exception as e:
            raise DecodingError(
                f"Unexpected error deserializing property '{prop_def.name}' at offset {offset}: {e}"
            ) from e

    @staticmethod
    def _deserialize_atom_property(data: bytes, offset: int, prop_def: PropertyDefinition,
                                   num_atoms: Optional[int] = None) -> Tuple[Any, int]:
        """Deserialize atomic property - unified handling for scalars and arrays"""
        # Check bounds
        if offset >= len(data):
            raise DecodingError(f"Insufficient data: offset {offset} >= data length {len(data)}")
        
        # Read count flag/byte
        count_flag = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
        offset += 1
        
        if count_flag == PropertySerializer.SINGLE_VALUE_FLAG:
            # Single value (scalar or multi-dimensional element)
            value, offset = PropertySerializer._deserialize_element(data, offset, prop_def)
            if num_atoms is not None and num_atoms > 1:
                # Repeat for all atoms
                return [value] * num_atoms, offset
            else:
                # For single atom or None, return just the value
                return value, offset
        else:
            # Multiple values
            if count_flag == PropertySerializer.LONG_COUNT_FLAG:
                # Check bounds before reading 4-byte count
                if offset + 4 > len(data):
                    raise DecodingError(
                        f"Insufficient data for long count: need 4 bytes at offset {offset}"
                    )
                count = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
            else:
                count = count_flag
            
            # Validate count: must be 1 (single value repeated) or num_atoms (one per atom)
            if num_atoms is not None and count != 1 and count != num_atoms:
                raise DecodingError(
                    f"Atomic property count mismatch: expected 1 or {num_atoms}, got {count}"
                )
            
            # Validate count is reasonable
            if count < 0 or count > 1000000:  # Reasonable upper bound
                raise DecodingError(f"Invalid count value: {count}")
            
            values = []
            for i in range(count):
                atom_value, offset = PropertySerializer._deserialize_element(data, offset, prop_def)
                values.append(atom_value)
            
            return values, offset
    
    @staticmethod
    def _deserialize_structure_property(data: bytes, offset: int,
                                       prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize structure-level property - unified handling for scalars and arrays"""
        # Structure properties don't have count encoding, just deserialize the value
        return PropertySerializer._deserialize_element(data, offset, prop_def)
    
    @staticmethod
    def _deserialize_multi_dimensional(data: bytes, offset: int,
                                      prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize multi-dimensional array element"""
        dim = prop_def.dimensions[0]
        
        # Calculate required size and check bounds
        if prop_def.data_type in (float, tuple):
            size = dim * 4
            if offset + size > len(data):
                raise DecodingError(
                    f"Insufficient data for multi-dimensional value: need {size} bytes at offset {offset}"
                )
            values = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, dim),
                                 data[offset:offset+size])
            return tuple(values), offset + size
        elif prop_def.data_type == int:
            size = dim * 4
            if offset + size > len(data):
                raise DecodingError(
                    f"Insufficient data for multi-dimensional value: need {size} bytes at offset {offset}"
                )
            values = struct.unpack(BinaryFormat.array(BinaryFormat.INT32, dim),
                                 data[offset:offset+size])
            return tuple(values), offset + size
        elif prop_def.data_type == bool:
            if offset + dim > len(data):
                raise DecodingError(
                    f"Insufficient data for multi-dimensional value: need {dim} bytes at offset {offset}"
                )
            bool_values = struct.unpack(BinaryFormat.array(BinaryFormat.UINT8, dim),
                                      data[offset:offset+dim])
            return tuple(bool(x) for x in bool_values), offset + dim
        else:
            raise DecodingError(f"Unsupported multi-dimensional type: {prop_def.data_type}")
    
    @staticmethod
    def _deserialize_element(data: bytes, offset: int,
                            prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize a single element - unified handling for scalars and multi-dimensional values"""
        if prop_def.dimensions:
            # Multi-dimensional element
            return PropertySerializer._deserialize_multi_dimensional(data, offset, prop_def)
        else:
            # Scalar element
            return PropertySerializer._deserialize_scalar_value(data, offset, prop_def)
    
    @staticmethod
    def _deserialize_scalar_value(data: bytes, offset: int,
                                 prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize scalar value (used for both structure and atomic properties)"""
        handler = PropertySerializer.TYPE_HANDLERS.get(prop_def.data_type)
        if not handler:
            raise DecodingError(f"Unsupported scalar data type: {prop_def.data_type}")
        
        if prop_def.data_type == str:
            return PropertySerializer._deserialize_string(data, offset)
        
        # For scalar values, prefer element_format (space-efficient) when available,
        # fallback to single_value_format (higher precision)
        fmt = handler.get('element_format') or handler.get('single_value_format')
        if fmt:
            size = struct.calcsize(fmt)
            if offset + size > len(data):
                raise DecodingError(
                    f"Insufficient data for scalar value: need {size} bytes at offset {offset}"
                )
            value = struct.unpack(fmt, data[offset:offset+size])[0]
            return value, offset + size
        raise DecodingError(f"Format not defined for {prop_def.data_type}")
    
    @staticmethod
    def _deserialize_string(data: bytes, offset: int) -> Tuple[str, int]:
        """Deserialize string with efficient length encoding"""
        if offset >= len(data):
            raise DecodingError(f"Insufficient data for string length: offset {offset} >= data length {len(data)}")
        
        encoded_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
        offset += 1
        
        if encoded_len == PropertySerializer.LONG_COUNT_FLAG:
            if offset + 4 > len(data):
                raise DecodingError(
                    f"Insufficient data for long string length: need 4 bytes at offset {offset}"
                )
            encoded_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
            offset += 4
        
        # Validate string length is reasonable
        if encoded_len < 0 or encoded_len > 10000000:  # 10MB max string size
            raise DecodingError(f"Invalid string length: {encoded_len}")
        
        if offset + encoded_len > len(data):
            raise DecodingError(
                f"Insufficient data for string content: need {encoded_len} bytes at offset {offset}"
            )
        
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
        try:
            return all(isinstance(x, (int, float)) for x in value)
        except (TypeError, ValueError):
            # If iteration fails or elements are not comparable, it's not a multi-dimensional element
            return False
    
    @staticmethod
    def _is_list_of_multi_dimensional_elements(value: Any) -> bool:
        """Check if value is a list of multi-dimensional elements"""
        if not PropertySerializer._is_sequence(value) or len(value) == 0:
            return False
        
        # Check if first element is a multi-dimensional element
        try:
            first_elem = value[0]
            return PropertySerializer._is_multi_dimensional_element(first_elem)
        except (IndexError, TypeError):
            return False
    
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
                # Allow lists/tuples of expected type for atomic properties
                elif (prop_def.is_per_atom and 
                      isinstance(value, (list, tuple)) and 
                      len(value) > 0 and
                      num_atoms is not None and
                      num_atoms > 1):
                    # This could be a list of elements - will validate structure later
                    pass
                else:
                    return False
        
        # For atomic properties, validate structure
        if prop_def.is_per_atom and prop_def.dimensions:
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
            try:
                if len(value) != prop_def.dimensions[0]:
                    return False
                # For multi-dimensional elements, check that all elements are numbers
                if not all(isinstance(x, (int, float)) for x in value):
                    return False
            except (TypeError, ValueError):
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
        
        if not prop_def.dimensions:  # Scalar property (no dimensions)
            if prop_def.data_type == str:
                if not isinstance(value, str):
                    return 0
                return handler['single_value_size'](value)
            return handler['single_value_size']
        else:
            if prop_def.is_per_atom:  # Atomic property
                # Check if this is a single multi-dimensional element
                if PropertySerializer._is_multi_dimensional_element(value) and prop_def.dimensions:
                    actual_count = 1
                else:
                    actual_count = PropertySerializer._get_atom_count(value, num_atoms)
                
                # Count encoding size
                count_size = 1  # Default to 1 byte for count
                if actual_count > PropertySerializer.LONG_COUNT_FLAG - 1:
                    count_size = 5  # 1 byte flag + 4 bytes count
                
                if actual_count is None or actual_count <= 0:
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
                        if hasattr(value, '__getitem__') and value:
                            try:
                                element_size = handler['element_size'](value[0])
                            except (IndexError, TypeError, ValueError):
                                element_size = 50  # Default estimate
                        else:
                            element_size = 50  # Default estimate
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
                        if not isinstance(value, str):
                            return 0
                        return handler['element_size'](value)
                    return handler['element_size']
        
        return 0
