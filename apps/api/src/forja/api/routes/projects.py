from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from forja.api.errors import not_found
from forja.api.schemas import ProjectCreate, ProjectOut, ProjectUpdate, SavedPipeline
from forja.domain.migrations import migrate
from forja.domain.pipeline import Pipeline
from forja.storage.db import ProjectRow, get_session, utcnow
from forja.storage.repos import ProjectRepo

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
    )


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
    return _out(ProjectRepo(db).create(body.name, body.pipeline))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Db) -> ProjectOut:
    return _out(_get(db, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def rename_project(project_id: str, body: ProjectUpdate, db: Db) -> ProjectOut:
    row = _get(db, project_id)
    row.name = body.name
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
    return SavedPipeline(pipeline=body, version=row.version, updated_at=row.updated_at)
