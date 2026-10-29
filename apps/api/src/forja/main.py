from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from forja.api import errors
from forja.api.routes import auth, exports, formula, meta, pipeline, projects, sources, templates
from forja.api.security import current_user
from forja.nodes.registry import all_specs
from forja.settings import get_settings

log = logging.getLogger("forja")


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().db_url)
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().auto_migrate:
        run_migrations()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Forja API", version="0.1.0", lifespan=lifespan, description="Construtor visual de datasets.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Forja-Rows", "X-Forja-Has-More", "X-Forja-Cached"],
    )
    errors.install(app)
    # /health, /nodes and /auth are public; everything else needs a logged-in user.
    app.include_router(meta.router)
    app.include_router(auth.router)
    for r in (projects.router, sources.router, pipeline.router, formula.router, exports.router, templates.router):
        app.include_router(r, dependencies=[Depends(current_user)])

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        # Node configs aren't route models (they're validated per node), so publish them explicitly
        # for the generated TypeScript types.
        comps = schema.setdefault("components", {}).setdefault("schemas", {})
        for spec in all_specs():
            js = spec.config_model.model_json_schema(ref_template="#/components/schemas/{model}")
            for name, sub in js.pop("$defs", {}).items():
                comps.setdefault(name, sub)
            comps[spec.config_model.__name__] = js
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app


app = create_app()
