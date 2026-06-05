"""Numpy-aware helpers used by serializer validation and size estimation."""

from __future__ import annotations

from typing import Any

import numpy as np


def is_numpy_array(value: Any) -> bool:
    return isinstance(value, np.ndarray)


def to_python_sequence(value: Any) -> Any:
    return value.tolist() if isinstance(value, np.ndarray) else value
