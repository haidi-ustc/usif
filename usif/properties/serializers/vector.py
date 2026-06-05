"""Vector serializer aliases.

USIF's binary property format stores vectors and fixed-length tensor rows using
one dimensional records.  This module provides a named boundary for vector
semantics while delegating the shared binary mechanics to ``tensor``.
"""

from __future__ import annotations

from usif.properties.serializers.tensor import deserialize_multi_dimensional, serialize_multi_dimensional

serialize_vector = serialize_multi_dimensional
deserialize_vector = deserialize_multi_dimensional

__all__ = ["serialize_vector", "deserialize_vector"]
