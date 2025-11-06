#!/usr/bin/env python3
"""
USIF Constants
Binary format constants and utilities
"""


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

