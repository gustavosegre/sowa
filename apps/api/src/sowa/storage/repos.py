"""Repositories over the metadata DB."""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sowa.domain.pipeline import Flow, Pipeline
from sowa.domain.schema import Schema
from sowa.nodes.base import SourceInfo
from sowa.storage.db import (
    ExportJobRow,
    PipelineVersionRow,
    ProjectRow,
    SourceRow,
    TemplateRow,
    utcnow,
)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


class ProjectRepo:
    def __init__(self, s: Session) -> None:
        self.s = s

    def list(self) -> Sequence[ProjectRow]:
        return self.s.scalars(select(ProjectRow).order_by(ProjectRow.updated_at.desc())).all()

    def get(self, project_id: str) -> ProjectRow | None:
        return self.s.get(ProjectRow, project_id)

    def create(self, name: str, pipeline: Pipeline | None = None, workspace: str | None = None) -> ProjectRow:
        row = ProjectRow(
            id=new_id("prj"),
            name=name,
            pipeline=(pipeline or Pipeline()).model_dump(mode="json"),
            workspace=workspace,
        )
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


AUTO_SNAPSHOT_EVERY = timedelta(minutes=2)
MAX_VERSIONS = 100


class VersionRepo:
    """Pipeline history: automatic snapshots while editing + named versions."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def list(self, project_id: str) -> Sequence[PipelineVersionRow]:
        q = select(PipelineVersionRow).where(PipelineVersionRow.project_id == project_id)
        return self.s.scalars(q.order_by(PipelineVersionRow.created_at.desc(), PipelineVersionRow.id.desc())).all()

    def get(self, project_id: str, version_id: int) -> PipelineVersionRow | None:
        row = self.s.get(PipelineVersionRow, version_id)
        return row if row is not None and row.project_id == project_id else None

    def snapshot(self, project: ProjectRow, label: str | None = None) -> PipelineVersionRow:
        row = PipelineVersionRow(
            project_id=project.id,
            version=project.version,
            label=label,
            pipeline=project.pipeline,
            node_count=len((project.pipeline or {}).get("nodes", [])),
        )
        self.s.add(row)
        self.s.flush()
        self._prune(project.id)
        return row

    def maybe_snapshot(self, project: ProjectRow) -> None:
        """Called on every save; keeps at most one automatic snapshot per interval."""
        last = self.s.scalars(
            select(PipelineVersionRow)
            .where(PipelineVersionRow.project_id == project.id)
            .order_by(PipelineVersionRow.created_at.desc())
            .limit(1)
        ).first()
        created = last.created_at if last else None
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created is None or utcnow() - created >= AUTO_SNAPSHOT_EVERY:
            self.snapshot(project)

    def _prune(self, project_id: str) -> None:
        auto = [v for v in self.list(project_id) if v.label is None]
        for old in auto[MAX_VERSIONS:]:
            self.s.delete(old)


class TemplateRepo:
    def __init__(self, s: Session) -> None:
        self.s = s

    def list(self) -> Sequence[TemplateRow]:
        return self.s.scalars(select(TemplateRow).order_by(TemplateRow.name)).all()

    def get(self, template_id: str) -> TemplateRow | None:
        return self.s.get(TemplateRow, template_id)

    def create(self, name: str, description: str, flow: Flow) -> TemplateRow:
        row = TemplateRow(id=new_id("tpl"), name=name, description=description, flow=flow.model_dump(mode="json"))
        self.s.add(row)
        self.s.flush()
        return row

    def update(self, row: TemplateRow, name: str | None, description: str | None, flow: Flow | None) -> TemplateRow:
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if flow is not None:
            row.flow = flow.model_dump(mode="json")
            row.version += 1  # sub-flows compare this to offer "Atualizar"
        row.updated_at = utcnow()
        self.s.flush()
        return row

    def delete(self, row: TemplateRow) -> None:
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
    from sowa.deps import get_storage

    schema = Schema.model_validate({"columns": row.schema or []})
    path = None
    if row.status == "ready":
        # Rebuilt from the storage layout (not the stored absolute path), fetched if missing.
        st = get_storage()
        path = st.ensure_local(st.parquet_path(row.id)).as_posix()
    return SourceInfo(
        id=row.id,
        name=row.name,
        status=row.status,
        parquet_path=path,
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

    def finished_before(self, cutoff: datetime) -> Sequence[ExportJobRow]:
        q = select(ExportJobRow).where(ExportJobRow.status.in_(("done", "error")), ExportJobRow.created_at < cutoff)
        return self.s.scalars(q).all()
