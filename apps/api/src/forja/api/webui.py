"""The built web app served by the API (`make start`): one process, no Node at runtime, as in Flowa.

The front calls the API under `/api` (in `make dev` the Vite proxy strips it); here a small ASGI
wrapper strips it, so the same build works in both modes.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

DEFAULT_DIST = Path(__file__).resolve().parents[4] / "web" / "dist"


class StripApiPrefix:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            path: str = scope["path"]
            if path == "/api" or path.startswith("/api/"):
                scope = {**scope, "path": path[4:] or "/", "raw_path": (path[4:] or "/").encode()}
        await self.app(scope, receive, send)


def mount_web(app: FastAPI, dist: Path) -> bool:
    """Serves `dist` at `/` after the API routes (which keep priority). False when not built."""
    if not (dist / "index.html").is_file():
        return False
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return True
