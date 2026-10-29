from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from forja.api.errors import not_found
from forja.api.schemas import (
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    SavedPipeline,
    VersionCreate,
    VersionDetail,
    VersionOut,
)
from forja.domain.migrations import migrate
from forja.domain.pipeline import Pipeline
from forja.storage.db import PipelineVersionRow, ProjectRow, get_session, utcnow
from forja.storage.repos import ProjectRepo, VersionRepo

router = APIRouter(prefix="/projects", tags=["projects"])
Db = Annotated[Session, Depends(get_session)]


def _out(row: ProjectRow) -> ProjectOut:
    return ProjectOut(
        id=row.id,
        name=row.name,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        node_count=len((row.pipeline or {}).get("nodes", [])),
        workspace=row.workspace,
    )


def _workspace(name: str | None) -> str | None:
    return " ".join((name or "").split()) or None


def _get(db: Session, project_id: str) -> ProjectRow:
    row = ProjectRepo(db).get(project_id)
    if row is None:
        raise not_found("Projeto")
    return row


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Db) -> list[ProjectOut]:
    return [_out(r) for r in ProjectRepo(db).list()]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: Db) -> ProjectOut:
    return _out(ProjectRepo(db).create(body.name, body.pipeline, workspace=_workspace(body.workspace)))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Db) -> ProjectOut:
    return _out(_get(db, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, db: Db) -> ProjectOut:
    """Rename and/or move to another workspace."""
    row = _get(db, project_id)
    if body.name is not None:
        row.name = body.name
    if "workspace" in body.model_fields_set:
        row.workspace = _workspace(body.workspace)
    row.updated_at = utcnow()
    return _out(row)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Db) -> None:
    ProjectRepo(db).delete(_get(db, project_id))


@router.get("/{project_id}/pipeline", response_model=SavedPipeline)
def load_pipeline(project_id: str, db: Db) -> SavedPipeline:
    row = _get(db, project_id)
    return SavedPipeline(pipeline=migrate(dict(row.pipeline or {})), version=row.version, updated_at=row.updated_at)


@router.put("/{project_id}/pipeline", response_model=SavedPipeline)
def save_pipeline(project_id: str, body: Pipeline, db: Db) -> SavedPipeline:
    row = ProjectRepo(db).save_pipeline(_get(db, project_id), body)
    VersionRepo(db).maybe_snapshot(row)
    return SavedPipeline(pipeline=body, version=row.version, updated_at=row.updated_at)


def _version_out(v: PipelineVersionRow) -> VersionOut:
    return VersionOut(id=v.id, version=v.version, label=v.label, node_count=v.node_count, created_at=v.created_at)


@router.get("/{project_id}/versions", response_model=list[VersionOut])
def list_versions(project_id: str, db: Db) -> list[VersionOut]:
    """History: automatic snapshots while editing and named versions."""
    _get(db, project_id)
    return [_version_out(v) for v in VersionRepo(db).list(project_id)]


@router.post("/{project_id}/versions", response_model=VersionOut, status_code=201)
def create_version(project_id: str, body: VersionCreate, db: Db) -> VersionOut:
    """Save the current pipeline as a named version."""
    return _version_out(VersionRepo(db).snapshot(_get(db, project_id), body.label))


@router.get("/{project_id}/versions/{version_id}", response_model=VersionDetail)
def get_version(project_id: str, version_id: int, db: Db) -> VersionDetail:
    v = VersionRepo(db).get(project_id, version_id)
    if v is None:
        raise not_found("Versão")
    return VersionDetail(**_version_out(v).model_dump(), pipeline=migrate(dict(v.pipeline)))


@router.post("/{project_id}/versions/{version_id}/restore", response_model=SavedPipeline)
def restore_version(project_id: str, version_id: int, db: Db) -> SavedPipeline:
    """Restore a version. The current state is saved first, so restoring can be undone."""
    row = _get(db, project_id)
    repo = VersionRepo(db)
    v = repo.get(project_id, version_id)
    if v is None:
        raise not_found("Versão")
    repo.snapshot(row, "Antes de restaurar")
    pipeline = migrate(dict(v.pipeline))
    row = ProjectRepo(db).save_pipeline(row, pipeline)
    return SavedPipeline(pipeline=pipeline, version=row.version, updated_at=row.updated_at)
