"""HTTP error handling: every error leaves the API as a pt-BR `ApiError`."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from forja.api.schemas import ApiError
from forja.compiler.analyze import pydantic_message
from forja.compiler.build import CompileError
from forja.domain.issues import Issue
from forja.domain.migrations import PipelineVersionError
from forja.engine.duck import EngineError
from forja.io.importers.tabular import ImportError_


class HttpError(Exception):
    def __init__(self, status: int, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = ApiError(code=code, message=message, hint=hint)


def not_found(what: str) -> HttpError:
    return HttpError(404, "NOT_FOUND", f"{what} não encontrado.")


def _issue_body(issue: Issue, issues: list[Issue] | None = None) -> dict[str, object]:
    return ApiError(
        code=issue.code.value, message=issue.message, hint=issue.hint, detail=issue.detail, issues=issues or [issue]
    ).model_dump(mode="json")


def install(app: FastAPI) -> None:
    @app.exception_handler(HttpError)
    async def _http(_: Request, e: HttpError) -> JSONResponse:
        return JSONResponse(e.body.model_dump(mode="json"), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        first = e.errors()[0] if e.errors() else {"type": "", "msg": "", "loc": ()}
        loc = ".".join(str(x) for x in first["loc"] if x not in ("body", "query", "path")) or "requisição"
        body = ApiError(
            code="INVALID_REQUEST",
            message=f'Dados inválidos em "{loc}": {pydantic_message(first)}.',
            detail=str(e.errors())[:2000],
        )
        return JSONResponse(body.model_dump(mode="json"), status_code=422)

    @app.exception_handler(CompileError)
    async def _compile(_: Request, e: CompileError) -> JSONResponse:
        return JSONResponse(_issue_body(e.issues[0], e.issues), status_code=422)

    @app.exception_handler(EngineError)
    async def _engine(_: Request, e: EngineError) -> JSONResponse:
        status = 408 if e.issue.code.value == "TIMEOUT" else 422
        return JSONResponse(_issue_body(e.issue), status_code=status)

    @app.exception_handler(ImportError_)
    async def _import(_: Request, e: ImportError_) -> JSONResponse:
        return JSONResponse(ApiError(code=e.code.value, message=e.message).model_dump(mode="json"), status_code=422)

    @app.exception_handler(PipelineVersionError)
    async def _version(_: Request, e: PipelineVersionError) -> JSONResponse:
        return JSONResponse(ApiError(code="PIPELINE_VERSION", message=str(e)).model_dump(mode="json"), status_code=422)
