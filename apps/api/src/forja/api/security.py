"""Access token on every route except /health, /nodes and /auth/status (see forja.auth)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from forja.api.errors import HttpError
from forja.auth import AuthSettings, get_auth, is_loopback, token_ok

_bearer = HTTPBearer(auto_error=False, description="Token de acesso da Forja")


def unauthenticated() -> HttpError:
    return HttpError(
        401,
        "UNAUTHENTICATED",
        "Informe o token de acesso para continuar.",
        hint="Abra o endereço com #token= que a API mostra ao iniciar, ou rode `python -m forja.cli token`.",
    )


def local_only() -> HttpError:
    return HttpError(
        403,
        "LOCAL_ONLY",
        "O login está desligado (FORJA_AUTH_ENABLED=false): só aceito conexões desta máquina.",
        hint="Ligue o login para acessar de outro computador.",
    )


def check_local(request: Request) -> None:
    """With login off, only loopback clients are answered."""
    if not is_loopback(request.client.host if request.client else ""):
        raise local_only()


def authenticated(request: Request, credentials: HTTPAuthorizationCredentials | None, auth: AuthSettings) -> bool:
    if auth.token is None:
        check_local(request)
        return True
    return credentials is not None and token_ok(credentials.credentials, auth)


def require_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """FastAPI dependency: 401 unless the request carries the access token."""
    if not authenticated(request, credentials, get_auth()):
        raise unauthenticated()


Bearer = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
