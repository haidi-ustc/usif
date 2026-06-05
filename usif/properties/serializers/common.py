"""Shared primitives for binary property serializers."""

from __future__ import annotations

from typing import Any, Optional

from usif.constants import BinaryFormat

SINGLE_VALUE_FLAG = 0
LONG_COUNT_FLAG = 255


def get_string_size(value: str) -> int:
    """Calculate encoded string size including length prefix."""
    if not isinstance(value, str):
        raise ValueError(f"Expected string, got {type(value)}")
    encoded_len = len(value.encode("utf-8"))
    return 1 + encoded_len if encoded_len <= 255 else 5 + encoded_len


TYPE_HANDLERS = {
    float: {"format": BinaryFormat.FLOAT64, "size": 8},
    int: {"format": BinaryFormat.INT64, "size": 8},
    bool: {"format": BinaryFormat.BOOL, "size": 1},
    str: {"format": None, "size": get_string_size},
    tuple: {"format": BinaryFormat.FLOAT64, "size": lambda dim: dim * 8},
}


def is_sequence(value: Any) -> bool:
    """Return True for sequence-like values except text/bytes."""
    return hasattr(value, "__len__") and not isinstance(value, (str, bytes))


def is_multi_dimensional_element(value: Any) -> bool:
    """Return True for one numeric vector/tensor row rather than a list of atom values."""
    if not is_sequence(value):
        return False
    if isinstance(value, (str, bytes)):
        return False
    try:
        return all(isinstance(x, (int, float)) for x in value)
    except (TypeError, ValueError):
        return False


def is_list_of_multi_dimensional_elements(value: Any) -> bool:
    """Return True when value looks like a list of numeric vectors."""
    if not is_sequence(value) or len(value) == 0:
        return False
    try:
        return is_multi_dimensional_element(value[0])
    except (IndexError, TypeError):
        return False


def get_atom_count(value: Any, num_atoms: Optional[int]) -> int:
    """Return the encoded atom-value count for per-atom property values."""
    if is_sequence(value) and not is_multi_dimensional_element(value):
        return len(value)
    return 1
