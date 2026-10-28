from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from forja.api.errors import HttpError, not_found
from forja.api.schemas import ExportJobOut, ExportRequest
from forja.compiler.analyze import analyze
from forja.compiler.build import CompileError
from forja.domain.issues import Issue
from forja.jobs import exports as jobs
from forja.nodes.output import OutputConfig
from forja.storage.db import ExportJobRow, get_session
from forja.storage.repos import DbSourceResolver, ExportRepo

router = APIRouter(prefix="/exports", tags=["exports"])
Db = Annotated[Session, Depends(get_session)]

MEDIA = {
    ".csv": "text/csv",
    ".parquet": "application/vnd.apache.parquet",
    ".json": "application/json",
    ".ndjson": "application/x-ndjson",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _out(row: ExportJobRow) -> ExportJobOut:
    return ExportJobOut(
        id=row.id,
        node_id=row.node_id,
        status=row.status,
        progress=row.progress,
        format=row.format,
        filename=row.filename,
        rows=row.rows,
        size_bytes=row.size_bytes,
        error=Issue.model_validate(row.error) if row.error else None,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


@router.post("", response_model=ExportJobOut, status_code=202)
def start_export(body: ExportRequest, db: Db) -> ExportJobOut:
    """Start an export job for an `output` node."""
    a = analyze(body.pipeline, DbSourceResolver(db))
    r = a.results.get(body.node_id)
    if r is None or r.node.type != "output" or not isinstance(r.config, OutputConfig):
        raise HttpError(422, "NOT_AN_OUTPUT", 'Escolha um nó "Exportar" para gerar o arquivo.')
    if not r.ok:
        raise CompileError([i for i in r.issues if i.severity != "warning"])
    row = ExportRepo(db).create(
        project_id=body.project_id,
        node_id=body.node_id,
        format=r.config.format,
        filename=r.config.filename,
        status="pending",
    )
    db.commit()
    jobs.submit(row.id, body.pipeline, body.node_id)
    return _out(row)


@router.get("/{job_id}", response_model=ExportJobOut)
def get_export(job_id: str, db: Db) -> ExportJobOut:
    row = ExportRepo(db).get(job_id)
    if row is None:
        raise not_found("Exportação")
    return _out(row)


@router.get("/{job_id}/download", response_class=FileResponse)
def download(job_id: str, db: Db) -> FileResponse:
    row = ExportRepo(db).get(job_id)
    if row is None:
        raise not_found("Exportação")
    if row.status != "done" or not row.file_path or not Path(row.file_path).exists():
        raise HttpError(409, "EXPORT_NOT_READY", "O arquivo ainda não está pronto.")
    path = Path(row.file_path)
    return FileResponse(path, filename=path.name, media_type=MEDIA.get(path.suffix, "application/octet-stream"))
