from __future__ import annotations

import time
from functools import cache
from typing import Any

from forja.settings import get_settings
from forja.storage.files import LocalFileStorage, S3FileStorage


@cache
def get_storage() -> LocalFileStorage:
    s = get_settings()
    root = s.data_dir / "files"
    if s.storage == "local":
        return LocalFileStorage(root)
    try:
        import boto3
    except ImportError:
        raise RuntimeError("FORJA_STORAGE=s3 precisa do pacote boto3: instale com `uv sync --extra s3`.") from None
    if not s.s3_bucket:
        raise RuntimeError("FORJA_STORAGE=s3 precisa de FORJA_S3_BUCKET.")
    client = boto3.client("s3", endpoint_url=s.s3_endpoint_url, region_name=s.s3_region)
    if s.s3_create_bucket:
        _create_bucket(client, s.s3_bucket)
    return S3FileStorage(root, client, s.s3_bucket, s.s3_prefix)


def _create_bucket(client: Any, bucket: str, attempts: int = 30) -> None:
    """Dev only: wait for the S3 server (it may start after the API) and create the bucket."""
    for i in range(attempts):
        try:
            client.head_bucket(Bucket=bucket)
            return
        except Exception:
            try:
                client.create_bucket(Bucket=bucket)
                return
            except Exception:
                if i == attempts - 1:
                    raise
                time.sleep(1)
