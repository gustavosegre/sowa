"""FileStorage backed by an S3-compatible bucket (CLAUDE.md §4), with an in-memory client."""

from __future__ import annotations

import io
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from forja.storage.files import S3FileStorage
from test_api import confirm, upload, wait_export


class FakeS3:
    """Just enough of boto3's S3 client: objects in a dict, 2 keys per listing page."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None:  # noqa: N803
        self.objects[(Bucket, Key)] = Path(Filename).read_bytes()

    def download_file(self, Bucket: str, Key: str, Filename: str) -> None:  # noqa: N803
        if (Bucket, Key) not in self.objects:
            raise FileNotFoundError(Key)
        Path(Filename).write_bytes(self.objects[(Bucket, Key)])

    def list_objects_v2(self, **kw: Any) -> dict[str, Any]:
        keys = sorted(k for b, k in self.objects if b == kw["Bucket"] and k.startswith(kw["Prefix"]))
        start = int(kw.get("ContinuationToken", 0))
        page = keys[start : start + 2]
        more = start + 2 < len(keys)
        return {
            "Contents": [{"Key": k} for k in page],
            "IsTruncated": more,
            **({"NextContinuationToken": str(start + 2)} if more else {}),
        }

    def delete_objects(self, **kw: Any) -> dict[str, Any]:
        for o in kw["Delete"]["Objects"]:
            self.objects.pop((kw["Bucket"], o["Key"]), None)
        return {}


def test_files_survive_losing_the_local_disk(tmp_path: Path) -> None:
    s3 = FakeS3()
    st = S3FileStorage(tmp_path / "a", s3, "bucket", prefix="/forja/")
    original = st.original_path("src_1", "vendas.csv")
    size, _ = st.save_stream(io.BytesIO(b"uf;valor\nPR;1\n"), original, max_bytes=1000)
    st.persist(original)
    st.persist(st.parquet_path("src_1"))  # not written yet: nothing to upload
    assert set(s3.objects) == {("bucket", "forja/sources/src_1/original_vendas.csv")}

    # A new machine (empty disk) with the same bucket.
    shutil.rmtree(tmp_path / "a")
    other = S3FileStorage(tmp_path / "b", s3, "bucket", prefix="forja")
    path = other.ensure_local(other.original_path("src_1", "vendas.csv"))
    assert path.read_bytes() == b"uf;valor\nPR;1\n"
    assert size == len(path.read_bytes())

    missing = other.ensure_local(other.parquet_path("src_1"))
    assert not missing.exists()
    assert not missing.with_name("normalized.parquet.part").exists()


def test_delete_source_removes_every_object_of_it(tmp_path: Path) -> None:
    s3 = FakeS3()
    st = S3FileStorage(tmp_path, s3, "bucket")
    for name in ("a", "b", "c", "d", "e"):
        f = st.work_dir("src_1") / name
        f.write_text(name)
        st.persist(f)
    keep = st.original_path("src_2", "x.csv")
    keep.write_text("x")
    st.persist(keep)
    st.delete_source("src_1")
    assert set(s3.objects) == {("bucket", "sources/src_2/original_x.csv")}
    assert not (tmp_path / "sources" / "src_1").exists()


def test_api_with_s3_storage_survives_losing_the_disk(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from forja import deps
    from forja.api.routes import exports as export_routes
    from forja.api.routes import sources as source_routes
    from forja.jobs import exports as export_jobs

    s3 = FakeS3()
    st = S3FileStorage(deps.get_storage().root, s3, "bucket", "forja")
    for mod in (deps, source_routes, export_routes, export_jobs):
        monkeypatch.setattr(mod, "get_storage", lambda: st)

    up = upload(client, "vendas_latin1.csv")
    confirm(client, up)
    sid = up["source"]["id"]
    keys = {k for _, k in s3.objects}
    assert {f"forja/sources/{sid}/normalized.parquet", f"forja/sources/{sid}/original_vendas_latin1.csv"} <= keys

    shutil.rmtree(st.root / "sources" / sid)  # e.g. a new container
    pipeline = {
        "nodes": [
            {"id": "s", "type": "source", "config": {"source_id": sid}},
            {"id": "o", "type": "output", "config": {"format": "csv", "filename": "saida"}},
        ],
        "edges": [{"id": "e", "source": "s", "target": "o"}],
    }
    prev = client.post("/pipeline/preview", json={"pipeline": pipeline, "node_id": "s", "limit": 10})
    assert prev.status_code == 200, prev.text
    assert prev.headers["x-forja-rows"] == "4"

    job = wait_export(client, client.post("/exports", json={"pipeline": pipeline, "node_id": "o"}).json()["id"])
    assert job["status"] == "done", job
    assert f"forja/exports/{job['id']}/saida.csv" in {k for _, k in s3.objects}
    shutil.rmtree(st.root / "exports" / job["id"])
    r = client.get(f"/exports/{job['id']}/download")
    assert r.status_code == 200
    assert r.content.count(b"\n") == 5
