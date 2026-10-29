"""Basic username/password login (CLAUDE.md §19)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from forja.auth import hash_password, verify_password
from forja.settings import get_settings


@pytest.fixture
def auth_on(client: TestClient) -> Iterator[TestClient]:
    s = get_settings()
    s.auth_enabled = True
    client.cookies.clear()
    try:
        yield client
    finally:
        s.auth_enabled = False
        client.cookies.clear()


def test_password_hash() -> None:
    h = hash_password("segredo123")
    assert h.startswith("scrypt$")
    assert verify_password("segredo123", h)
    assert not verify_password("segredo124", h)
    assert not verify_password("x", "lixo")


def test_login_flow(auth_on: TestClient) -> None:
    c = auth_on
    assert c.get("/health").status_code == 200
    r = c.get("/projects")
    assert r.status_code == 401
    assert r.json()["message"] == "Faça login para continuar."

    st = c.get("/auth/status").json()
    assert st == {"auth_enabled": True, "setup_required": True, "user": None}

    short = c.post("/auth/setup", json={"username": "ana", "password": "curta"})
    assert short.status_code == 422
    assert short.json()["message"] == 'Dados inválidos em "password": texto curto demais (limite: 8).'
    r = c.post("/auth/setup", json={"username": "ana", "password": "senha-forte"})
    assert r.status_code == 201
    assert c.get("/auth/status").json()["user"]["username"] == "ana"
    assert c.post("/auth/setup", json={"username": "bia", "password": "senha-forte"}).status_code == 409

    # Logged in: the project records who created it.
    p = c.post("/projects", json={"name": "Do login"}).json()
    assert p["owner"] == "ana"
    assert any(x["id"] == p["id"] and x["owner"] == "ana" for x in c.get("/projects").json())

    # Another user, created by ana; same workspace.
    assert c.post("/auth/users", json={"username": "bia", "password": "outra-senha"}).status_code == 201
    assert c.post("/auth/users", json={"username": "bia", "password": "outra-senha"}).status_code == 409
    assert [u["username"] for u in c.get("/auth/users").json()] == ["ana", "bia"]

    assert c.post("/auth/logout").status_code == 204
    assert c.get("/projects").status_code == 401
    bad = c.post("/auth/login", json={"username": "bia", "password": "errada-123"})
    assert bad.status_code == 401
    assert bad.json()["message"] == "Usuário ou senha incorretos."
    assert c.post("/auth/login", json={"username": "bia", "password": "outra-senha"}).status_code == 200
    assert any(x["id"] == p["id"] for x in c.get("/projects").json())
    assert c.post("/auth/users", json={"username": "zeca", "password": "12345678"}).status_code == 201
