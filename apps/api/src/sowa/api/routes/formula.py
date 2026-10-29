from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlglot import exp

from sowa.api.schemas import FormulaCheckOut, FormulaCheckRequest, FormulaRenderRequest, FunctionOut, FunctionParamOut
from sowa.compiler.build import CompileError, compile_chain
from sowa.domain.issues import Issue
from sowa.domain.schema import Schema
from sowa.domain.types import LogicalType, label
from sowa.engine.describe import analyze_live
from sowa.engine.duck import EngineError, get_engine
from sowa.formula.functions import FUNCTIONS
from sowa.formula.parser import FormulaSyntaxError, parse
from sowa.formula.render import render
from sowa.formula.service import compile_formula, formula_issue
from sowa.formula.typecheck import FormulaError
from sowa.nodes.base import alias, col
from sowa.storage.db import get_session
from sowa.storage.repos import DbSourceResolver

router = APIRouter(prefix="/formula", tags=["formula"])
Db = Annotated[Session, Depends(get_session)]


@router.get("/functions", response_model=list[FunctionOut])
def functions() -> list[FunctionOut]:
    """Function catalog (autocomplete and help)."""
    out: list[FunctionOut] = []
    for f in FUNCTIONS:
        en = f.aliases[0] if f.aliases else f.name
        out.append(
            FunctionOut(
                name=f.name,
                aliases=list(f.aliases),
                category=f.category,
                context=f.context,
                signature=f.signature(";"),
                signature_en=f.signature(",").replace(f.name, en, 1),
                params=[
                    FunctionParamOut(name=p.name, type=p.type.value, optional=p.optional, variadic=p.variadic)
                    for p in f.params
                ],
                returns=label(f.returns) if isinstance(f.returns, LogicalType) else None,
                description=f.description,
                example=f.example,
                excel=f.excel,
            )
        )
    return out


def _fmt(v: Any, locale: str) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return ("VERDADEIRO" if v else "FALSO") if locale == "pt-BR" else ("TRUE" if v else "FALSE")
    if isinstance(v, dt.datetime):
        return v.strftime("%d/%m/%Y %H:%M:%S" if locale == "pt-BR" else "%Y-%m-%d %H:%M:%S")
    if isinstance(v, dt.date):
        return v.strftime("%d/%m/%Y" if locale == "pt-BR" else "%Y-%m-%d")
    if isinstance(v, (float, Decimal)):
        s = f"{float(v):.10g}"
        return s.replace(".", ",") if locale == "pt-BR" else s
    return str(v)


@router.post("/check", response_model=FormulaCheckOut)
def check(body: FormulaCheckRequest, db: Db) -> FormulaCheckOut:
    """Validate a formula: result type, positioned errors and up to 10 example values."""
    schema = Schema(columns=body.columns or [])
    upstream: str | None = None
    analysis = None
    if body.pipeline is not None and body.node_id is not None:
        analysis = analyze_live(body.pipeline, DbSourceResolver(db))
        r = analysis.results.get(body.node_id)
        if r is not None:
            upstream = r.inputs.get("in")
            if upstream and (s := analysis.results[upstream].schema) is not None:
                schema = s
    try:
        params = body.pipeline.settings.params if body.pipeline is not None else []
        f = compile_formula(
            body.formula, schema, locale=body.locale, context=body.context, group_keys=body.group_keys, params=params
        )
    except FormulaError as e:
        return FormulaCheckOut(ok=False, issues=[formula_issue(e)])
    examples: list[str | None] = []
    issues: list[Issue] = []
    if analysis is not None and upstream is not None and analysis.results[upstream].ok:
        try:
            chain = compile_chain(analysis, upstream)
            src = exp.Table(this=exp.to_identifier(upstream, quoted=True))
            q = exp.select(alias(f.sql, "__v")).from_(src)
            if body.context == "aggregate" and body.group_keys:
                q = q.group_by(*[col(k) for k in body.group_keys])
            rows = get_engine().rows(chain.wrap(q.limit(10)), timeout=5)
            examples = [_fmt(r[0], body.locale) for r in rows]
        except (CompileError, EngineError) as e:
            issues.extend(e.issues if isinstance(e, CompileError) else [e.issue])
    return FormulaCheckOut(
        ok=True, type=f.type, type_label=label(f.type), examples=examples, issues=issues, columns=f.columns
    )


@router.post("/render", response_model=str)
def render_formula(body: FormulaRenderRequest) -> str:
    """Re-render a formula in another locale (argument and decimal separators, function names)."""
    try:
        return render(parse(body.formula, body.from_locale), body.to_locale)
    except FormulaSyntaxError:
        return body.formula
