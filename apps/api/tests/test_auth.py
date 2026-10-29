"""Access token, as in Flowa (CLAUDE.md §19)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from conftest import TOKEN
from sowa import auth
from sowa.cli import main as cli
from sowa.settings import get_settings


@pytest.fixture
def anon(client: TestClient) -> TestClient:
    """Same app, without the Authorization header."""
    return TestClient(client.app)


@pytest.fixture
def token_settings() -> Iterator[None]:
    """Lets a test change auth settings; restores them and the cached token afterwards."""
    s = get_settings()
    saved = (s.auth_enabled, s.token)
    try:
        yield
    finally:
        s.auth_enabled, s.token = saved
        auth.get_auth.cache_clear()


def test_token_required(client: TestClient, anon: TestClient) -> None:
    assert anon.get("/health").status_code == 200
    assert anon.get("/nodes").status_code == 200
    r = anon.get("/projects")
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHENTICATED"
    assert r.json()["message"] == "Informe o token de acesso para continuar."
    assert anon.get("/projects", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert anon.get("/projects", headers={"Authorization": f"Basic {TOKEN}"}).status_code == 401
    assert anon.get("/projects", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200

    assert anon.get("/auth/status").json() == {"auth_enabled": True, "authenticated": False}
    assert client.get("/auth/status").json() == {"auth_enabled": True, "authenticated": True}


def test_token_file_generated(token_settings: None) -> None:
    s = get_settings()
    s.token = ""
    auth.token_path().unlink(missing_ok=True)
    first = auth.resolve_token()
    assert first.token
    assert len(first.token) >= 40
    assert first.source == str(auth.token_path())
    assert auth.token_path().read_text(encoding="utf-8") == first.token
    assert auth.resolve_token().token == first.token  # reused on the next start

    s.token = "da-variavel"
    assert auth.resolve_token() == auth.AuthSettings("da-variavel", "SOWA_TOKEN")
    s.auth_enabled = False
    assert auth.resolve_token().token is None


def test_cli_prints_url_and_rotates(token_settings: None, capsys: pytest.CaptureFixture[str]) -> None:
    s = get_settings()
    s.token = ""
    cli(["token"])
    old = auth.token_path().read_text(encoding="utf-8")
    assert f"{s.web_url}/#token={old}" in capsys.readouterr().out
    cli(["token", "--new"])
    new = auth.token_path().read_text(encoding="utf-8")
    assert new != old
    assert f"#token={new}" in capsys.readouterr().out
    s.token = "da-variavel"
    with pytest.raises(SystemExit):
        cli(["token", "--new"])


def test_login_off_only_answers_this_machine(client: TestClient, token_settings: None) -> None:
    get_settings().auth_enabled = False
    auth.get_auth.cache_clear()
    remote = TestClient(client.app, client=("192.168.0.10", 50000))
    r = remote.get("/projects")
    assert r.status_code == 403
    assert r.json()["code"] == "LOCAL_ONLY"
    local = TestClient(client.app, client=("127.0.0.1", 50000))
    assert local.get("/projects").status_code == 200
    assert local.get("/auth/status").json() == {"auth_enabled": False, "authenticated": True}


def test_signed_download_link(client: TestClient, anon: TestClient) -> None:
    access = auth.get_auth()
    query = auth.sign_download("exp_x", access, now=1_000)
    exp, sig = (part.split("=")[1] for part in query.split("&"))
    assert auth.download_ok("exp_x", int(exp), sig, access) is False  # expired long ago
    query = auth.sign_download("exp_x", access)
    exp, sig = (part.split("=")[1] for part in query.split("&"))
    assert auth.download_ok("exp_x", int(exp), sig, access)
    assert not auth.download_ok("exp_y", int(exp), sig, access)  # bound to the job id
    # Unknown job, valid signature: passes auth and gets 404; bad signature: 401.
    assert anon.get(f"/exports/exp_x/download?{query}").status_code == 404
    r = anon.get(f"/exports/exp_x/download?exp={exp}&sig={'0' * 64}")
    assert r.status_code == 401
    assert r.json()["code"] == "LINK_EXPIRED"
    assert anon.get("/exports/exp_x/download").json()["code"] == "UNAUTHENTICATED"


def test_project_workspaces(client: TestClient) -> None:
    p = client.post("/projects", json={"name": "Vendas", "workspace": "  Comercial  "}).json()
    assert p["workspace"] == "Comercial"
    r = client.patch(f"/projects/{p['id']}", json={"name": "Vendas 2026"}).json()
    assert (r["name"], r["workspace"]) == ("Vendas 2026", "Comercial")  # untouched when not sent
    assert client.patch(f"/projects/{p['id']}", json={"workspace": "RH"}).json()["workspace"] == "RH"
    assert client.patch(f"/projects/{p['id']}", json={"workspace": ""}).json()["workspace"] is None
    assert client.post("/projects", json={"name": "Solto"}).json()["workspace"] is None
