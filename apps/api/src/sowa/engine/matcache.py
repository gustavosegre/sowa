"""Materialized cache (CLAUDE.md §13): results of `cacheable` nodes as Parquet, keyed by node hash.

The node hash covers type + config + upstream hashes + source files, so editing
a node invalidates it and everything after it, and nothing else. Entries are
evicted least-recently-used once the directory passes `max_bytes`.
"""

from __future__ import annotations

import os
import threading
import time
from functools import cache
from pathlib import Path

from sqlglot import exp

from sowa.engine.duck import Engine
from sowa.io.sql import copy_to


class MaterializedCache:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.parquet"

    def lookup(self, key: str) -> str | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            os.utime(p)  # LRU: last use
        except OSError:
            return None
        return p.as_posix()

    def materialize(self, engine: Engine, query: exp.Select, key: str) -> str:
        """Write `query` (a full statement) to the cache under `key` and return the file path."""
        found = self.lookup(key)
        if found:
            return found
        dest = self._path(key)
        tmp = dest.with_name(f".{key}.{threading.get_ident()}.tmp.parquet")
        try:
            engine.execute(copy_to(query, tmp, format="PARQUET", compression="zstd"))
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
        self.evict()
        return dest.as_posix()

    def evict(self) -> None:
        with self._lock:
            files = [(p, p.stat()) for p in self.root.glob("*.parquet") if not p.name.startswith(".")]
            total = sum(s.st_size for _, s in files)
            for p, s in sorted(files, key=lambda f: f[1].st_mtime):
                if total <= self.max_bytes:
                    break
                # Keep anything used in the last few seconds (it may be read right now).
                if time.time() - s.st_mtime < 5:
                    continue
                p.unlink(missing_ok=True)
                total -= s.st_size

    def clear(self) -> None:
        with self._lock:
            for p in self.root.glob("*.parquet"):
                p.unlink(missing_ok=True)


@cache
def get_cache() -> MaterializedCache:
    from sowa.deps import get_storage
    from sowa.settings import get_settings

    return MaterializedCache(get_storage().cache_dir() / "nodes", int(get_settings().cache_max_gb * 1024**3))
