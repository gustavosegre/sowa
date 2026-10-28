from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from forja.api.errors import HttpError, not_found
from forja.api.schemas import TemplateCreate, TemplateDetail, TemplateOut, TemplateUpdate
from forja.domain.pipeline import Flow
from forja.nodes.subflow import FORBIDDEN
from forja.storage.db import TemplateRow, get_session
from forja.storage.repos import TemplateRepo

router = APIRouter(prefix="/templates", tags=["templates"])
Db = Annotated[Session, Depends(get_session)]


def _out(row: TemplateRow) -> TemplateOut:
    flow = Flow.model_validate(row.flow)
    plain = not any(n.type in FORBIDDEN for n in flow.nodes)
    return TemplateOut(
        id=row.id,
        name=row.name,
        description=row.description,
        version=row.version,
        node_count=len(flow.nodes),
        inputs=[i.name for i in flow.inputs],
        can_be_subflow=bool(flow.inputs) and flow.output is not None and plain,
        updated_at=row.updated_at,
    )


def _detail(row: TemplateRow) -> TemplateDetail:
    return TemplateDetail(**_out(row).model_dump(), flow=Flow.model_validate(row.flow))


def _get(db: Session, template_id: str) -> TemplateRow:
    row = TemplateRepo(db).get(template_id)
    if row is None:
        raise not_found("Template")
    return row


def _check(flow: Flow) -> Flow:
    """Structural consistency only; node configs are validated when the template is used."""
    ids = {n.id for n in flow.nodes}
    problem = None
    if not flow.nodes:
        problem = "o template não tem nós"
    elif len(ids) != len(flow.nodes):
        problem = "há nós com o mesmo id"
    elif any(e.source not in ids or e.target not in ids for e in flow.edges):
        problem = "há conexões com nós fora do template"
    elif any(t.node not in ids for i in flow.inputs for t in i.targets):
        problem = "uma entrada aponta para um nó fora do template"
    elif flow.output is not None and flow.output not in ids:
        problem = "a saída aponta para um nó fora do template"
    if problem:
        raise HttpError(422, "INVALID_TEMPLATE", f"Template inválido: {problem}.")
    return flow


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Db) -> list[TemplateOut]:
    return [_out(r) for r in TemplateRepo(db).list()]


@router.post("", response_model=TemplateDetail, status_code=201)
def create_template(body: TemplateCreate, db: Db) -> TemplateDetail:
    return _detail(TemplateRepo(db).create(body.name, body.description, _check(body.flow)))


@router.get("/{template_id}", response_model=TemplateDetail)
def get_template(template_id: str, db: Db) -> TemplateDetail:
    return _detail(_get(db, template_id))


@router.put("/{template_id}", response_model=TemplateDetail)
def update_template(template_id: str, body: TemplateUpdate, db: Db) -> TemplateDetail:
    flow = _check(body.flow) if body.flow is not None else None
    return _detail(TemplateRepo(db).update(_get(db, template_id), body.name, body.description, flow))


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, db: Db) -> None:
    TemplateRepo(db).delete(_get(db, template_id))
