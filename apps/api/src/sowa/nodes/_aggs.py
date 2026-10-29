"""Aggregation functions shared by group_by, pivot and window (CLAUDE.md §9)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error
from sowa.domain.schema import Schema
from sowa.domain.types import NUMERIC_TYPES, LogicalType, label
from sowa.formula.functions import tmpl
from sowa.nodes.base import col, count_star, lit

L = LogicalType

AggFn = Literal[
    "count",
    "count_non_null",
    "count_distinct",
    "sum",
    "avg",
    "median",
    "min",
    "max",
    "stddev",
    "variance",
    "percentile",
    "mode",
    "first",
    "last",
    "concat",
]

AGG_LABELS: dict[str, str] = {
    "count": "Contagem de linhas",
    "count_non_null": "Contagem de não vazios",
    "count_distinct": "Contagem distinta",
    "sum": "Soma",
    "avg": "Média",
    "median": "Mediana",
    "min": "Mínimo",
    "max": "Máximo",
    "stddev": "Desvio padrão",
    "variance": "Variância",
    "percentile": "Percentil",
    "mode": "Moda",
    "first": "Primeiro",
    "last": "Último",
    "concat": "Concatenar texto",
}

_NUMERIC_ONLY = {"sum", "avg", "median", "stddev", "variance", "percentile"}


class Aggregation(BaseModel):
    column: str | None = None  # None only for "count"
    fn: AggFn = "sum"
    as_: str = Field(default="", alias="as")
    percentile: float = Field(default=0.5, ge=0, le=1)
    separator: str = ", "
    order_by: str | None = None  # for first/last/concat

    model_config = {"populate_by_name": True}

    def output_name(self) -> str:
        if self.as_.strip():
            return self.as_
        if self.fn == "count":
            return "contagem"
        return f"{self.fn}_{self.column}"


def agg_type(a: Aggregation, schema: Schema) -> LogicalType:
    if a.fn in ("count", "count_non_null", "count_distinct"):
        return L.INTEGER
    src = schema.type_of(a.column) if a.column and schema.has(a.column) else L.DECIMAL
    if a.fn == "sum":
        return L.INTEGER if src is L.INTEGER else L.DECIMAL
    if a.fn in ("avg", "median", "stddev", "variance", "percentile"):
        return L.DECIMAL
    if a.fn == "concat":
        return L.TEXT
    return src


def validate_agg(a: Aggregation, schema: Schema, where: str | None) -> list[Issue]:
    issues: list[Issue] = []
    if a.fn != "count":
        if not a.column:
            return [error(IssueCode.INVALID_CONFIG, f'Escolha a coluna para "{AGG_LABELS[a.fn]}".')]
        c = schema.get(a.column)
        if c is None:
            return [column_not_found(a.column, where=where)]
        if a.fn in _NUMERIC_ONLY and c.type not in NUMERIC_TYPES:
            issues.append(
                error(
                    IssueCode.TYPE_MISMATCH,
                    f'"{AGG_LABELS[a.fn]}" precisa de números, mas "{a.column}" é {label(c.type)}.',
                    column=a.column,
                    hint='Converta a coluna com o nó "Alterar tipo".',
                )
            )
    if a.order_by and not schema.has(a.order_by):
        issues.append(column_not_found(a.order_by, where=where))
    return issues


def agg_expr(a: Aggregation, schema: Schema, filter_: exp.Expr | None = None) -> exp.Expr:
    """Aggregate expression; `filter_` adds `FILTER (WHERE ...)` (used by pivot)."""
    c = col(a.column) if a.column else None
    src_t = schema.type_of(a.column) if a.column and schema.has(a.column) else None
    e: exp.Expr
    match a.fn:
        case "count":
            e = count_star()
        case "count_non_null":
            assert c is not None
            e = exp.Count(this=c)
        case "count_distinct":
            assert c is not None
            e = exp.Count(this=exp.Distinct(expressions=[c]))
        case "sum":
            e = exp.Sum(this=c)
        case "avg":
            e = exp.Avg(this=c)
        case "median":
            e = exp.func("MEDIAN", c)
        case "min":
            e = exp.Min(this=c)
        case "max":
            e = exp.Max(this=c)
        case "stddev":
            e = exp.func("STDDEV_SAMP", c)
        case "variance":
            e = exp.func("VAR_SAMP", c)
        case "percentile":
            e = exp.func("QUANTILE_CONT", c, lit(a.percentile))
        case "mode":
            e = exp.func("MODE", c)
        case "first":
            e = exp.func("ARG_MIN", c, col(a.order_by)) if a.order_by else exp.func("FIRST", c)
        case "last":
            e = exp.func("ARG_MAX", c, col(a.order_by)) if a.order_by else exp.func("LAST", c)
        case "concat":
            assert c is not None
            if a.order_by:
                e = tmpl("STRING_AGG(CAST(_0 AS VARCHAR), _1 ORDER BY _2)", c, lit(a.separator), col(a.order_by))
            else:
                e = tmpl("STRING_AGG(CAST(_0 AS VARCHAR), _1)", c, lit(a.separator))
    if filter_ is not None:
        e = exp.Filter(this=e, expression=exp.Where(this=filter_))
    # Keep result types stable and Arrow-friendly (no HUGEINT for integer sums).
    out_t = agg_type(a, schema)
    if out_t is L.INTEGER:
        e = exp.Cast(this=e, to=exp.DataType.build("BIGINT"))
    elif a.fn in ("avg", "median", "stddev", "variance", "percentile") or (a.fn == "sum" and src_t is L.INTEGER):
        e = exp.Cast(this=e, to=exp.DataType.build("DOUBLE"))
    return e
