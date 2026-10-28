"""File storage behind an interface (CLAUDE.md §4).

DuckDB reads and writes local paths, so every implementation exposes a local
directory layout. `LocalFileStorage` is the dev/default implementation; an
S3-compatible implementation must sync objects into the same layout.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol


class FileStorage(Protocol):
    root: Path

    def original_path(self, source_id: str, filename: str) -> Path: ...
    def parquet_path(self, source_id: str) -> Path: ...
    def work_dir(self, source_id: str) -> Path: ...
    def export_dir(self, job_id: str) -> Path: ...
    def cache_dir(self) -> Path: ...
    def temp_dir(self) -> Path: ...
    def save_stream(self, stream: BinaryIO, dest: Path, max_bytes: int) -> tuple[int, str]: ...
    def delete_source(self, source_id: str) -> None: ...


class UploadTooLarge(Exception):
    pass


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        for d in ("sources", "exports", "cache", "tmp"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

    def _source_dir(self, source_id: str) -> Path:
        d = self.root / "sources" / source_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def original_path(self, source_id: str, filename: str) -> Path:
        safe = "".join(ch for ch in Path(filename).name if ch not in '\\/:*?"<>|') or "arquivo"
        return self._source_dir(source_id) / f"original_{safe}"

    def parquet_path(self, source_id: str) -> Path:
        return self._source_dir(source_id) / "normalized.parquet"

    def work_dir(self, source_id: str) -> Path:
        d = self._source_dir(source_id) / "work"
        d.mkdir(exist_ok=True)
        return d

    def export_dir(self, job_id: str) -> Path:
        d = self.root / "exports" / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def cache_dir(self) -> Path:
        return self.root / "cache"

    def temp_dir(self) -> Path:
        return self.root / "tmp"

    def save_stream(self, stream: BinaryIO, dest: Path, max_bytes: int) -> tuple[int, str]:
        """Copy an upload to disk in chunks; returns (size, sha256)."""
        h = hashlib.sha256()
        size = 0
        with dest.open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise UploadTooLarge
                h.update(chunk)
                out.write(chunk)
        return size, h.hexdigest()

    def delete_source(self, source_id: str) -> None:
        shutil.rmtree(self.root / "sources" / source_id, ignore_errors=True)
