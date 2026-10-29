"""Local everyday use (`make start`): built web app served by the API, /api prefix, export retention."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from forja.api.webui import StripApiPrefix, mount_web
from forja.deps import get_storage
from forja.jobs.exports import purge_old
from forja.settings import get_settings
from forja.storage.db import ExportJobRow, session_scope, utcnow
from forja.storage.repos import ExportRepo


def test_api_prefix_is_stripped(client: TestClient) -> None:
    assert client.get("/api/health").json() == client.get("/health").json()
    assert client.get("/api/projects").status_code == 200
    assert TestClient(client.app).get("/api/projects").status_code == 401  # still needs the token


def test_built_web_app_is_served(tmp_path: Path) -> None:
    assert not mount_web(FastAPI(), tmp_path)  # not built: nothing mounted
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Forja</title>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    app = FastAPI()
    app.add_middleware(StripApiPrefix)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    assert mount_web(app, tmp_path)
    c = TestClient(app)
    assert "<title>Forja</title>" in c.get("/").text
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
