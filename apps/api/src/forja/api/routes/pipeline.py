from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from forja.api.errors import HttpError
from forja.api.schemas import (
    DistinctOut,
    DistinctRequest,
    NodeAnalysisOut,
    NodeRequest,
    PipelineRequest,
    PreviewRequest,
    ProfileOut,
    ProfileRequest,
    SchemaResponse,
    SqlOut,
    StatsOut,
)
from forja.compiler.analyze import Analysis, analyze
from forja.compiler.build import CompileError, compile_chain, to_sql
from forja.compiler.hashing import node_hashes
from forja.domain.pipeline import Pipeline
from forja.engine import service
from forja.engine.duck import get_engine
from forja.settings import get_settings
from forja.storage.db import get_session
from forja.storage.repos import DbSourceResolver

router = APIRouter(tags=["pipeline"])
Db = Annotated[Session, Depends(get_session)]


def _analysis(p: Pipeline, db: Session) -> Analysis:
    return analyze(p, DbSourceResolver(db))


def _node(a: Analysis, node_id: str) -> None:
    if node_id not in a.results:
        raise HttpError(404, "NODE_NOT_FOUND", "Nó não encontrado no fluxo.")


def _require_ok(a: Analysis, node_id: str) -> None:
    _node(a, node_id)
    r = a.results[node_id]
    if not r.ok:
        raise CompileError([i for i in r.issues if i.severity != "warning"] or r.issues)


@router.post("/pipeline/schema", response_model=SchemaResponse)
def pipeline_schema(body: PipelineRequest, db: Db) -> SchemaResponse:
    """Schemas and issues of every node, without executing data. Called on every edit."""
    a = _analysis(body.pipeline, db)
    out: dict[str, NodeAnalysisOut] = {}
    for nid, r in a.results.items():
        hashes = node_hashes(a, nid) if r.ok else {}
        out[nid] = NodeAnalysisOut(
            status=r.status,
            columns=r.schema.columns if r.schema else None,
            issues=r.issues,
            changed_columns=r.changed_columns,
            input_columns={h: s.columns for h, u in r.inputs.items() if (s := a.results[u].schema) is not None},
            hash=hashes.get(nid),
        )
    return SchemaResponse(nodes=out)


@router.post(
    "/pipeline/preview",
    response_class=Response,
    responses={200: {"content": {"application/vnd.apache.arrow.stream": {}}}},
)
def pipeline_preview(body: PreviewRequest, db: Db) -> Response:
    a = _analysis(body.pipeline, db)
    _require_ok(a, body.node_id)
    s = get_settings()
    p = service.preview(
        get_engine(), a, body.node_id, limit=body.limit, offset=body.offset, timeout=s.preview_timeout_s
    )
    return Response(
        content=p.data,
        media_type="application/vnd.apache.arrow.stream",
        headers={
            "X-Forja-Rows": str(p.rows),
            "X-Forja-Has-More": "1" if p.has_more else "0",
            "X-Forja-Cached": "1" if p.cached else "0",
        },
    )


@router.post("/pipeline/stats", response_model=StatsOut)
def pipeline_stats(body: NodeRequest, db: Db) -> StatsOut:
    """Row counts (node + inputs) and data-dependent warnings. Runs in the background from the UI."""
    a = _analysis(body.pipeline, db)
    _require_ok(a, body.node_id)
    st = service.stats(get_engine(), a, body.node_id, get_settings().preview_timeout_s * 4)
    return StatsOut(row_count=st.row_count, input_row_counts=st.input_row_counts, issues=st.issues)


@router.post("/pipeline/profile", response_model=ProfileOut)
def pipeline_profile(body: ProfileRequest, db: Db) -> ProfileOut:
    a = _analysis(body.pipeline, db)
    _require_ok(a, body.node_id)
    schema = a.results[body.node_id].schema
    if schema is None or not schema.has(body.column):
        raise HttpError(404, "COLUMN_NOT_FOUND", f'A coluna "{body.column}" não existe neste nó.')
    data = service.profile(get_engine(), a, body.node_id, body.column, get_settings().preview_timeout_s * 2)
    return ProfileOut.model_validate(data)


@router.post("/pipeline/sql", response_model=SqlOut)
def pipeline_sql(body: NodeRequest, db: Db) -> SqlOut:
    """SQL compiled up to the node ("Copiar como SQL")."""
    a = _analysis(body.pipeline, db)
    _require_ok(a, body.node_id)
    return SqlOut(sql=to_sql(compile_chain(a, body.node_id, for_display=True).query(), pretty=True))


@router.post("/pivot/distinct-values", response_model=DistinctOut)
@router.post("/pipeline/distinct-values", response_model=DistinctOut)
def distinct_values(body: DistinctRequest, db: Db) -> DistinctOut:
    """Distinct values of a column, from the node's input (pivot/filter config) or output."""
    a = _analysis(body.pipeline, db)
    _node(a, body.node_id)
    target = body.node_id
    if body.of_input:
        r = a.results[body.node_id]
        up = r.inputs.get("in") or next(iter(r.inputs.values()), None)
        if up is None:
            raise HttpError(422, "MISSING_INPUT", "Conecte uma entrada ao nó primeiro.")
        target = up
    _require_ok(a, target)
    schema = a.results[target].schema
    if schema is None or not schema.has(body.column):
        raise HttpError(404, "COLUMN_NOT_FOUND", f'A coluna "{body.column}" não existe.')
    values, truncated = service.distinct_values(
        get_engine(), a, target, body.column, body.limit, get_settings().preview_timeout_s * 2
    )
    return DistinctOut(values=values, truncated=truncated)
