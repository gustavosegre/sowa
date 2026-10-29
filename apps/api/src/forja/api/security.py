"""Login required on every route except /health and /auth (when auth is enabled)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from forja.api.errors import HttpError
from forja.auth import COOKIE
from forja.settings import get_settings
from forja.storage.db import UserRow, get_session
from forja.storage.repos import SessionRepo


def unauthenticated() -> HttpError:
    return HttpError(401, "UNAUTHENTICATED", "Faça login para continuar.")


def current_user(request: Request, db: Annotated[Session, Depends(get_session)]) -> UserRow | None:
    """The logged-in user (None when auth is disabled). Raises 401 without a valid session."""
    if not get_settings().auth_enabled:
        return None
    token = request.cookies.get(COOKIE)
    user = SessionRepo(db).user(token) if token else None
    if user is None:
        raise unauthenticated()
    return user


CurrentUser = Annotated[UserRow | None, Depends(current_user)]
