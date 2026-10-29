"""Small thread-safe LRU caches for preview pages and row counts, keyed by node hash."""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Generic, TypeVar

V = TypeVar("V")


class LRU(Generic[V]):
    def __init__(self, max_items: int = 256, max_bytes: int | None = None) -> None:
        self.max_items = max_items
        self.max_bytes = max_bytes
        self._data: OrderedDict[str, tuple[V, int]] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> V | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            self._data.move_to_end(key)
            return item[0]

    def put(self, key: str, value: V, size: int = 0) -> None:
        with self._lock:
            if key in self._data:
                self._bytes -= self._data.pop(key)[1]
            self._data[key] = (value, size)
            self._bytes += size
            while len(self._data) > self.max_items or (
                self.max_bytes is not None and self._bytes > self.max_bytes and len(self._data) > 1
            ):
                _, (_, s) = self._data.popitem(last=False)
                self._bytes -= s

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._bytes = 0


preview_cache: LRU[bytes] = LRU(max_items=200, max_bytes=256 * 1024 * 1024)
count_cache: LRU[int] = LRU(max_items=5000)
