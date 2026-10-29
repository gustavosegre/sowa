"""Access token, following the Flowa pattern (CLAUDE.md §19).

Token source, in order: ``FORJA_TOKEN``, or a random token generated on first start and kept
in ``<data_dir>/token`` (readable only by the owner on POSIX). Every route except ``/health``,
``/nodes`` and ``/auth/status`` needs ``Authorization: Bearer <token>``. A header (never a
cookie or query string) also closes the CSRF path: a foreign page cannot send it.

Export downloads are plain browser links, so they carry a short-lived HMAC signature of the
job id instead of the token. With login off (``FORJA_AUTH_ENABLED=false``) only requests from
this machine are answered.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import time
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from forja.settings import get_settings

log = logging.getLogger("forja")

DOWNLOAD_TTL_S = 300


@dataclass(frozen=True)
class AuthSettings:
    token: str | None  # None = login off (loopback only)
    source: str


def token_path() -> Path:
    return get_settings().data_dir / "token"


def _read_token_file() -> str | None:
    try:
        return token_path().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def write_token_file(token: str) -> None:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        path.write_text(token, encoding="utf-8")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)
    os.chmod(path, 0o600)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def resolve_token(*, create: bool = True) -> AuthSettings:
    """The configured token, generating and saving one when none exists."""
    s = get_settings()
    if not s.auth_enabled:
        return AuthSettings(None, "FORJA_AUTH_ENABLED=false")
    if s.token.strip():
        return AuthSettings(s.token.strip(), "FORJA_TOKEN")
    saved = _read_token_file()
    if saved:
        return AuthSettings(saved, str(token_path()))
    if not create:
        return AuthSettings(None, "")
    token = new_token()
    write_token_file(token)
    log.info("[auth] novo token de acesso gerado em %s", token_path())
    return AuthSettings(token, str(token_path()))


@cache
def get_auth() -> AuthSettings:
    return resolve_token()


def token_ok(supplied: str, auth: AuthSettings) -> bool:
    return auth.token is not None and hmac.compare_digest(supplied.encode(), auth.token.encode())


def is_loopback(host: str) -> bool:
    host = host.strip("[]")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _signature(token: str, job_id: str, expires: int) -> str:
    return hmac.new(token.encode(), f"download:{job_id}:{expires}".encode(), hashlib.sha256).hexdigest()


def sign_download(job_id: str, auth: AuthSettings, now: float | None = None) -> str:
    """Query string for a download link (empty when login is off)."""
    if auth.token is None:
        return ""
    expires = int(now if now is not None else time.time()) + DOWNLOAD_TTL_S
    return f"exp={expires}&sig={_signature(auth.token, job_id, expires)}"


def download_ok(job_id: str, expires: int, sig: str, auth: AuthSettings) -> bool:
    if auth.token is None or expires < time.time():
        return False
    return hmac.compare_digest(sig, _signature(auth.token, job_id, expires))
