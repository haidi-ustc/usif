"""Thread-safe LRU cache used by USIF structure containers."""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Optional

from usif.structures.structure import USIFStructure


class StructureCache:
    """Small thread-safe LRU cache for decoded structures."""

    def __init__(self, capacity: int):
        self.capacity = max(0, capacity)
        self._items: OrderedDict[str, USIFStructure] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[USIFStructure]:
        if self.capacity == 0:
            return None
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key: str, value: USIFStructure) -> None:
        if self.capacity == 0:
            return
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._items

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
