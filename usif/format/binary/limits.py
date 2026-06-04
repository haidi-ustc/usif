"""Defensive limits for USIF binary decoding.

The limits are intentionally generous for scientific workloads while still
preventing malformed files from requesting unbounded memory or CPU.
"""

MAX_PAYLOAD_SIZE = 512 * 1024 * 1024  # 512 MiB uncompressed payload
MAX_COMPRESSED_SIZE = 512 * 1024 * 1024  # 512 MiB compressed payload
MAX_STRING_LENGTH = 1024 * 1024  # 1 MiB UTF-8 strings
MAX_PROPERTY_SECTION_SIZE = 128 * 1024 * 1024  # 128 MiB properties
MAX_PROPERTY_VALUE_SIZE = 64 * 1024 * 1024  # 64 MiB per property value
MAX_ATOM_COUNT = 10_000_000
MAX_SYMMETRIC_SITE_COUNT = 255  # stored as uint8 in v4
MAX_CUSTOM_PROPERTY_COUNT = 255
MAX_KNOWN_PROPERTY_COUNT = 255
