"""Repositories over the metadata DB."""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from forja.domain.pipeline import Pipeline
from forja.domain.schema import Schema
from forja.nodes.base import SourceInfo
from forja.storage.db import ExportJobRow, ProjectRow, SourceRow, utcnow


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


class ProjectRepo:
    def __init__(self, s: Session) -> None:
        self.s = s

    def list(self) -> Sequence[ProjectRow]:
        return self.s.scalars(select(ProjectRow).order_by(ProjectRow.updated_at.desc())).all()

    def get(self, project_id: str) -> ProjectRow | None:
        return self.s.get(ProjectRow, project_id)

    def create(self, name: str, pipeline: Pipeline | None = None) -> ProjectRow:
        row = ProjectRow(id=new_id("prj"), name=name, pipeline=(pipeline or Pipeline()).model_dump(mode="json"))
        self.s.add(row)
        self.s.flush()
        return row

    def save_pipeline(self, row: ProjectRow, pipeline: Pipeline) -> ProjectRow:
        row.pipeline = pipeline.model_dump(mode="json")
        row.version += 1
        row.updated_at = utcnow()
        self.s.flush()
        return row

    def delete(self, row: ProjectRow) -> None:
        self.s.delete(row)


class SourceRepo:
    def __init__(self, s: Session) -> None:
        self.s = s

    def get(self, source_id: str) -> SourceRow | None:
        return self.s.get(SourceRow, source_id)

    def list(self, project_id: str | None = None) -> Sequence[SourceRow]:
        q = select(SourceRow).order_by(SourceRow.created_at.desc())
        if project_id is not None:
            q = q.where(SourceRow.project_id == project_id)
        return self.s.scalars(q).all()

    def add(self, row: SourceRow) -> SourceRow:
        self.s.add(row)
        self.s.flush()
        return row

    def delete(self, row: SourceRow) -> None:
        self.s.delete(row)


def source_info(row: SourceRow) -> SourceInfo:
    schema = Schema.model_validate({"columns": row.schema or []})
    return SourceInfo(
        id=row.id,
        name=row.name,
        status=row.status,
        parquet_path=row.parquet_path,
        schema=schema,
        row_count=row.row_count,
        # Changes whenever the file or its import options change (cache key).
        sha256=f"{row.sha256}:{row.updated_at.isoformat() if row.updated_at else ''}",
    )


class DbSourceResolver:
    """SourceResolver backed by the DB, memoized for one request."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self._memo: dict[str, SourceInfo | None] = {}

    def get(self, source_id: str) -> SourceInfo | None:
        if source_id not in self._memo:
            row = self.s.get(SourceRow, source_id)
            self._memo[source_id] = source_info(row) if row else None
        return self._memo[source_id]


class ExportRepo:
    def __init__(self, s: Session) -> None:
        self.s = s

    def get(self, job_id: str) -> ExportJobRow | None:
        return self.s.get(ExportJobRow, job_id)

    def create(self, **fields: Any) -> ExportJobRow:
        row = ExportJobRow(id=new_id("exp"), **fields)
        self.s.add(row)
        self.s.flush()
        return row
