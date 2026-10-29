from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from sowa.api.errors import HttpError, not_found
from sowa.api.schemas import ApiError, ConfirmOut, DetectRequest, SourceOut, SourceRename, UploadOut
from sowa.deps import get_storage
from sowa.domain.schema import Schema
from sowa.engine.duck import EngineError, get_engine
from sowa.io.detect import detect_format
from sowa.io.importers.tabular import ImportError_, confirm, detect
from sowa.io.models import Detection, ImportOptions
from sowa.settings import get_settings
from sowa.storage.db import SourceRow, get_session, utcnow
from sowa.storage.files import UploadTooLarge
from sowa.storage.repos import ProjectRepo, SourceRepo, new_id

router = APIRouter(prefix="/sources", tags=["sources"])
Db = Annotated[Session, Depends(get_session)]


def _out(row: SourceRow) -> SourceOut:
    return SourceOut(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        filename=row.filename,
        format=row.format,
        size_bytes=row.size_bytes,
        status=row.status,
        row_count=row.row_count,
        columns=Schema.model_validate({"columns": row.schema}).columns if row.schema else None,
        options=ImportOptions.model_validate(row.options) if row.options else None,
        error=row.error,
        created_at=row.created_at,
    )


def _get(db: Session, source_id: str) -> SourceRow:
    row = SourceRepo(db).get(source_id)
    if row is None:
        raise not_found("Arquivo")
    return row


def _original(row: SourceRow) -> Path:
    st = get_storage()
    return st.ensure_local(st.original_path(row.id, row.filename))


def _detect(row: SourceRow, options: ImportOptions | None = None) -> Detection:
    st = get_storage()
    try:
        d = detect(get_engine(), row.format, _original(row), st.work_dir(row.id), options)
    except EngineError as e:
        raise ImportError_(f"Não foi possível ler o arquivo: {e.issue.message}") from e
    row.detected = d.model_dump(mode="json")
    return d


@router.post("", response_model=UploadOut, status_code=201)
def upload(db: Db, file: Annotated[UploadFile, File()], project_id: Annotated[str | None, Form()] = None) -> UploadOut:
    """Upload a file. Returns detected import settings and a sample (wizard step 2)."""
    if project_id and ProjectRepo(db).get(project_id) is None:
        raise not_found("Projeto")
    filename = Path(file.filename or "arquivo").name
    head = file.file.read(8)
    file.file.seek(0)
    fmt = detect_format(filename, head)
    if fmt is None:
        raise HttpError(
            415,
            "UNSUPPORTED_FORMAT",
            f'Formato de arquivo não suportado: "{filename}".',
            hint="Use CSV, TSV, TXT, Parquet, XLSX, JSON ou NDJSON.",
        )
    sid = new_id("src")
    st = get_storage()
    s = get_settings()
    try:
        size, sha = st.save_stream(file.file, st.original_path(sid, filename), s.max_upload_mb * 1024 * 1024)
    except UploadTooLarge:
        st.delete_source(sid)
        raise HttpError(413, "UPLOAD_TOO_LARGE", f"O arquivo passa do limite de {s.max_upload_mb} MB.") from None
    st.persist(st.original_path(sid, filename))
    row = SourceRepo(db).add(
        SourceRow(
            id=sid,
            project_id=project_id,
            name=Path(filename).stem,
            filename=filename,
            format=fmt,
            size_bytes=size,
            sha256=sha,
            status="pending",
        )
    )
    try:
        detection: Detection | None = _detect(row)
        error = None
    except ImportError_ as e:
        detection = None
        row.error = e.message
        error = ApiError(code=e.code.value, message=e.message)
    return UploadOut(source=_out(row), detection=detection, error=error)


@router.get("", response_model=list[SourceOut])
def list_sources(db: Db, project_id: str | None = None) -> list[SourceOut]:
    return [_out(r) for r in SourceRepo(db).list(project_id)]


@router.get("/{source_id}", response_model=SourceOut)
def get_source(source_id: str, db: Db) -> SourceOut:
    return _out(_get(db, source_id))


@router.get("/{source_id}/detection", response_model=Detection)
def get_detection(source_id: str, db: Db) -> Detection:
    row = _get(db, source_id)
    if row.detected:
        return Detection.model_validate(row.detected)
    return _detect(row)


@router.post("/{source_id}/detect", response_model=Detection)
def redetect(source_id: str, body: DetectRequest, db: Db) -> Detection:
    """Re-read the sample with edited settings (encoding, delimiter, header, sheet…)."""
    return _detect(_get(db, source_id), body.options)


@router.post("/{source_id}/confirm", response_model=ConfirmOut)
def confirm_import(source_id: str, body: ImportOptions, db: Db) -> ConfirmOut:
    """Confirm import options and column types -> normalized Parquet (zstd)."""
    row = _get(db, source_id)
    st = get_storage()
    dest = st.parquet_path(row.id)
    try:
        schema, report = confirm(get_engine(), row.format, _original(row), st.work_dir(row.id), dest, body)
    except EngineError as e:
        raise ImportError_(f"A importação falhou: {e.issue.message}", e.issue.code) from e
    st.persist(dest)
    row.options = body.model_dump(mode="json")
    row.schema = [c.model_dump(mode="json") for c in schema.columns]
    row.parquet_path = dest.resolve().as_posix()
    row.row_count = report.row_count
    row.status = "ready"
    row.error = None
    row.updated_at = utcnow()
    return ConfirmOut(source=_out(row), report=report)


@router.patch("/{source_id}", response_model=SourceOut)
def rename_source(source_id: str, body: SourceRename, db: Db) -> SourceOut:
    row = _get(db, source_id)
    row.name = body.name
    return _out(row)


@router.post("/{source_id}/replace", response_model=UploadOut)
def replace_file(source_id: str, db: Db, file: Annotated[UploadFile, File()]) -> UploadOut:
    """Replace the file ("Substituir fonte"), keeping the pipeline. The import must be confirmed again."""
    row = _get(db, source_id)
    filename = Path(file.filename or "arquivo").name
    head = file.file.read(8)
    file.file.seek(0)
    fmt = detect_format(filename, head)
    if fmt is None:
        raise HttpError(415, "UNSUPPORTED_FORMAT", f'Formato de arquivo não suportado: "{filename}".')
    st = get_storage()
    old_name = row.name
    st.delete_source(row.id)
    s = get_settings()
    try:
        size, sha = st.save_stream(file.file, st.original_path(row.id, filename), s.max_upload_mb * 1024 * 1024)
    except UploadTooLarge:
        raise HttpError(413, "UPLOAD_TOO_LARGE", f"O arquivo passa do limite de {s.max_upload_mb} MB.") from None
    st.persist(st.original_path(row.id, filename))
    row.filename, row.format, row.size_bytes, row.sha256 = filename, fmt, size, sha
    row.status, row.parquet_path, row.schema, row.row_count = "pending", None, None, None
    row.name = old_name
    row.updated_at = utcnow()
    previous = ImportOptions.model_validate(row.options) if row.options and row.format == fmt else None
    try:
        detection: Detection | None = _detect(row, None)
        if previous is not None and detection is not None:
            # Keep the user's column choices for columns that still exist.
            by_source = {c.source: c for c in previous.columns}
            detection.options.columns = [by_source.get(c.source, c) for c in detection.options.columns]
        error = None
    except ImportError_ as e:
        detection, error = None, ApiError(code=e.code.value, message=e.message)
    return UploadOut(source=_out(row), detection=detection, error=error)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: str, db: Db) -> None:
    row = _get(db, source_id)
    get_storage().delete_source(row.id)
    SourceRepo(db).delete(row)
