from __future__ import annotations

from fastapi import APIRouter, Request

from sowa.api.schemas import AuthStatus
from sowa.api.security import Bearer, authenticated
from sowa.auth import get_auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatus)
def status(request: Request, credentials: Bearer) -> AuthStatus:
    """Whether the access token is required and whether this request carries it."""
    auth = get_auth()
    return AuthStatus(auth_enabled=auth.token is not None, authenticated=authenticated(request, credentials, auth))
