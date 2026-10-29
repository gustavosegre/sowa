"""Local everyday use (`make start`): built web app served by the API, /api prefix, export retention."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sowa.api.webui import StripApiPrefix, mount_web
from sowa.deps import get_storage
from sowa.jobs.exports import purge_old
from sowa.settings import get_settings
from sowa.storage.db import ExportJobRow, session_scope, utcnow
from sowa.storage.repos import ExportRepo


def test_api_prefix_is_stripped(client: TestClient) -> None:
    assert client.get("/api/health").json() == client.get("/health").json()
    assert client.get("/api/projects").status_code == 200
    assert TestClient(client.app).get("/api/projects").status_code == 401  # still needs the token


def test_built_web_app_is_served(tmp_path: Path) -> None:
    assert not mount_web(FastAPI(), tmp_path)  # not built: nothing mounted
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>SOWA</title>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    app = FastAPI()
    app.add_middleware(StripApiPrefix)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    assert mount_web(app, tmp_path)
    c = TestClient(app)
    assert "<title>SOWA</title>" in c.get("/").text
    assert c.get("/?project=prj_1").status_code == 200
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/api/health").json() == {"status": "ok"}  # API routes keep priority


def test_old_exports_are_purged() -> None:
    st = get_storage()
    with session_scope() as s:
        repo = ExportRepo(s)
        old = repo.create(node_id="o", format="csv", filename="a", status="done")
        old.created_at = utcnow() - timedelta(days=get_settings().export_retention_days + 1)
        running = repo.create(node_id="o", format="csv", filename="b", status="running")
        running.created_at = old.created_at
        recent = repo.create(node_id="o", format="csv", filename="c", status="done")
        ids = (old.id, running.id, recent.id)
    for job_id in ids:
        (st.export_dir(job_id) / "x.csv").write_text("a;b\n", encoding="utf-8")

    assert purge_old() >= 1
    with session_scope() as s:
        assert s.get(ExportJobRow, ids[0]) is None
        assert s.get(ExportJobRow, ids[1]) is not None  # never while it is running
        assert s.get(ExportJobRow, ids[2]) is not None
    assert not (st.root / "exports" / ids[0]).exists()
    assert (st.root / "exports" / ids[2] / "x.csv").exists()


def test_legacy_forja_db_is_adopted(tmp_path: Path) -> None:
    from sowa.settings import _adopt_legacy_db

    (tmp_path / "forja.db").write_bytes(b"db")
    (tmp_path / "forja.db-wal").write_bytes(b"wal")
    _adopt_legacy_db(tmp_path)
    assert (tmp_path / "sowa.db").read_bytes() == b"db"
    assert (tmp_path / "sowa.db-wal").read_bytes() == b"wal"
    assert not (tmp_path / "forja.db").exists()
    (tmp_path / "forja.db").write_bytes(b"outro")
    _adopt_legacy_db(tmp_path)  # sowa.db already exists: nothing is overwritten
    assert (tmp_path / "sowa.db").read_bytes() == b"db"
