from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from forja.api.errors import HttpError
from forja.api.schemas import AuthStatus, Credentials, UserOut
from forja.api.security import CurrentUser, current_user
from forja.auth import COOKIE, hash_password, new_token, verify_password
from forja.settings import get_settings
from forja.storage.db import UserRow, get_session
from forja.storage.repos import SessionRepo, UserRepo

router = APIRouter(prefix="/auth", tags=["auth"])
Db = Annotated[Session, Depends(get_session)]
_DUMMY_HASH = hash_password(new_token())


def _out(u: UserRow) -> UserOut:
    return UserOut(id=u.id, username=u.username, created_at=u.created_at)


def _start_session(db: Session, user: UserRow, response: Response) -> None:
    s = get_settings()
    token = SessionRepo(db).create(user, s.session_days)
    response.set_cookie(
        COOKIE,
        token,
        max_age=s.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=s.cookie_secure,
        path="/",
    )


@router.get("/status", response_model=AuthStatus)
def status(request: Request, db: Db) -> AuthStatus:
    """Whether login is on, whether the first user must be created, and who is logged in."""
    s = get_settings()
    if not s.auth_enabled:
        return AuthStatus(auth_enabled=False, setup_required=False, user=None)
    token = request.cookies.get(COOKIE)
    user = SessionRepo(db).user(token) if token else None
    return AuthStatus(
        auth_enabled=True,
        setup_required=UserRepo(db).count() == 0,
        user=_out(user) if user else None,
    )


@router.post("/setup", response_model=UserOut, status_code=201)
def setup(body: Credentials, response: Response, db: Db) -> UserOut:
    """First run: create the first user and log in."""
    repo = UserRepo(db)
    if repo.count() > 0:
        raise HttpError(409, "ALREADY_SET_UP", "O primeiro usuário já foi criado. Faça login.")
    user = repo.create(body.username, body.password)
    _start_session(db, user, response)
    return _out(user)


@router.post("/login", response_model=UserOut)
def login(body: Credentials, response: Response, db: Db) -> UserOut:
    user = UserRepo(db).by_username(body.username)
    # Unknown user still pays for a scrypt, so timing doesn't reveal which usernames exist.
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok:
        raise HttpError(401, "INVALID_CREDENTIALS", "Usuário ou senha incorretos.")
    _start_session(db, user, response)
    return _out(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Db) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        SessionRepo(db).delete(token)
    response.delete_cookie(COOKIE, path="/")


@router.get("/users", response_model=list[UserOut], dependencies=[Depends(current_user)])
def list_users(db: Db) -> list[UserOut]:
    return [_out(u) for u in UserRepo(db).list()]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: Credentials, db: Db, user: CurrentUser) -> UserOut:
    """Any logged-in user can add another one (one shared workspace)."""
    repo = UserRepo(db)
    if repo.by_username(body.username) is not None:
        raise HttpError(409, "USERNAME_TAKEN", f'Já existe um usuário "{body.username}".')
    return _out(repo.create(body.username, body.password))
