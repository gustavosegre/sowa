"""File storage behind an interface (CLAUDE.md §4).

DuckDB reads and writes local paths only (it can't reach the network, §13), so every
implementation exposes a local directory layout. `LocalFileStorage` is the dev/default
implementation. `S3FileStorage` keeps the same layout as a working copy and an
S3-compatible bucket (MinIO in prod) as the durable store: durable files are uploaded
when written (`persist`) and downloaded when missing (`ensure_local`). The node cache
and temp files stay local only.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path
from typing import Any, BinaryIO, Protocol

log = logging.getLogger(__name__)


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
    def delete_export(self, job_id: str) -> None: ...
    # Durable files (originals, normalized Parquet, exports): call after writing / before reading.
    def persist(self, path: Path) -> None: ...
    def ensure_local(self, path: Path) -> Path: ...


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

    def delete_export(self, job_id: str) -> None:
        shutil.rmtree(self.root / "exports" / job_id, ignore_errors=True)

    def persist(self, path: Path) -> None:
        """The local disk is already the durable store."""

    def ensure_local(self, path: Path) -> Path:
        return path

    def key(self, path: Path) -> str:
        """Path relative to the storage root, with forward slashes."""
        return path.resolve().relative_to(self.root).as_posix()


class S3Client(Protocol):
    """The subset of boto3's S3 client used here."""

    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None: ...  # noqa: N803
    def download_file(self, Bucket: str, Key: str, Filename: str) -> None: ...  # noqa: N803
    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]: ...
    def delete_objects(self, **kwargs: Any) -> dict[str, Any]: ...


class S3FileStorage(LocalFileStorage):
    def __init__(self, root: Path, client: S3Client, bucket: str, prefix: str = "") -> None:
        super().__init__(root)
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""

    def _object(self, path: Path) -> str:
        return self.prefix + self.key(path)

    def persist(self, path: Path) -> None:
        if path.is_file():
            self.client.upload_file(Filename=str(path), Bucket=self.bucket, Key=self._object(path))

    def ensure_local(self, path: Path) -> Path:
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(f"{path.name}.part")
        try:
            self.client.download_file(Bucket=self.bucket, Key=self._object(path), Filename=str(part))
        except Exception:
            # Missing object: the caller reports the missing file as usual.
            log.warning("could not fetch %s from bucket %s", self._object(path), self.bucket, exc_info=True)
            part.unlink(missing_ok=True)
            return path
        part.replace(path)
        return path

    def delete_source(self, source_id: str) -> None:
        super().delete_source(source_id)
        self._delete_prefix(f"{self.prefix}sources/{source_id}/")

    def delete_export(self, job_id: str) -> None:
        super().delete_export(job_id)
        self._delete_prefix(f"{self.prefix}exports/{job_id}/")

    def _delete_prefix(self, prefix: str) -> None:
        # List everything first, then delete (at most 1000 keys per request).
        keys: list[str] = []
        token: str | None = None
        while True:
            extra = {"ContinuationToken": token} if token else {}
            page = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix, **extra)
            keys += [o["Key"] for o in page.get("Contents", [])]
            token = page.get("NextContinuationToken")
            if not page.get("IsTruncated") or not token:
                break
        for i in range(0, len(keys), 1000):
            batch = [{"Key": k} for k in keys[i : i + 1000]]
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch, "Quiet": True})
