from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field
from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error
from forja.domain.schema import Column, Schema
from forja.domain.types import NUMERIC_TYPES, LogicalType, label
from forja.nodes._aggs import AggFn, Aggregation, agg_expr, agg_type
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, lit, project
from forja.nodes.registry import register_node
from forja.nodes.sort import SortKey, order_expr

L = LogicalType

WindowFn = Literal[
    "row_number",
    "rank",
    "dense_rank",
    "cumulative_sum",
    "cumulative_count",
    "previous",
    "next",
    "pct_of_total",
    "moving_avg",
    "partition_agg",
]

FN_LABELS = {
    "row_number": "Número da linha",
    "rank": "Ranking",
    "dense_rank": "Ranking sem saltos",
    "cumulative_sum": "Soma acumulada",
    "cumulative_count": "Contagem acumulada",
    "previous": "Valor anterior",
    "next": "Próximo valor",
    "pct_of_total": "% do total",
    "moving_avg": "Média móvel",
    "partition_agg": "Agregação da partição",
}

_NEEDS_COLUMN = {"cumulative_sum", "previous", "next", "pct_of_total", "moving_avg", "partition_agg"}
_NEEDS_NUMBER = {"cumulative_sum", "pct_of_total", "moving_avg"}
_NEEDS_ORDER = {
    "row_number",
    "rank",
    "dense_rank",
    "cumulative_sum",
    "cumulative_count",
    "previous",
    "next",
    "moving_avg",
}


class WindowItem(BaseModel):
    fn: WindowFn = "cumulative_sum"
    column: str | None = None
    as_: str = Field(default="", alias="as")
    offset: int = Field(default=1, ge=1)  # previous/next
    size: int = Field(default=3, ge=1)  # moving average window (rows, including the current one)
    agg: AggFn = "sum"  # partition_agg

    model_config = {"populate_by_name": True}

    def output_name(self) -> str:
        return self.as_.strip() or (f"{self.fn}_{self.column}" if self.column else self.fn)


class WindowConfig(NodeConfig):
    partition_by: list[str] = []
    order_by: list[SortKey] = []
    items: list[WindowItem] = []


def item_type(it: WindowItem, schema: Schema) -> LogicalType:
    if it.fn in ("row_number", "rank", "dense_rank", "cumulative_count"):
        return L.INTEGER
    src = schema.type_of(it.column) if it.column and schema.has(it.column) else L.DECIMAL
    if it.fn in ("previous", "next"):
        return src
    if it.fn == "cumulative_sum":
        return L.INTEGER if src is L.INTEGER else L.DECIMAL
    if it.fn == "partition_agg":
        return agg_type(Aggregation(column=it.column, fn=it.agg), schema)
    return L.DECIMAL


@register_node
class WindowNode(NodeSpec[WindowConfig]):
    type = "window"
    config_model = WindowConfig
    label = "Janela"
    category = "aggregate"
    description = "Acumulado, ranking, anterior/próximo, % do total e média móvel por partição."

    def validate(self, cfg: WindowConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        where = ctx.input_labels.get("in")
        issues: list[Issue] = [column_not_found(n, where=where) for n in cfg.partition_by if not schema.has(n)]
        issues += [column_not_found(k.column, where=where) for k in cfg.order_by if not schema.has(k.column)]
        if not cfg.items:
            issues.append(error(IssueCode.INVALID_CONFIG, "Adicione pelo menos um cálculo."))
        names = set(schema.names)
        for it in cfg.items:
            if it.fn in _NEEDS_COLUMN:
                if not it.column:
                    issues.append(error(IssueCode.INVALID_CONFIG, f'Escolha a coluna para "{FN_LABELS[it.fn]}".'))
                    continue
                c = schema.get(it.column)
                if c is None:
                    issues.append(column_not_found(it.column, where=where))
                    continue
                if it.fn in _NEEDS_NUMBER and c.type not in NUMERIC_TYPES:
                    issues.append(
                        error(
                            IssueCode.TYPE_MISMATCH,
                            f'"{FN_LABELS[it.fn]}" precisa de números, mas "{it.column}" é {label(c.type)}.',
                            column=it.column,
                        )
                    )
            if it.fn in _NEEDS_ORDER and not cfg.order_by:
                issues.append(
                    error(
                        IssueCode.INVALID_CONFIG,
                        f'"{FN_LABELS[it.fn]}" depende da ordem das linhas: escolha "ordenar por".',
                    )
                )
            if it.output_name() in names:
                issues.append(error(IssueCode.DUPLICATE_COLUMN, f'Já existe uma coluna "{it.output_name()}".'))
            names.add(it.output_name())
        return issues

    def infer_schema(self, cfg: WindowConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        schema = inputs["in"]
        extra = [Column(name=it.output_name(), type=item_type(it, schema)) for it in cfg.items]
        return Schema(columns=[*schema.columns, *extra])

    def _expr(self, it: WindowItem, cfg: WindowConfig, schema: Schema) -> exp.Expr:
        part = [col(p) for p in cfg.partition_by]
        order = exp.Order(expressions=[order_expr(k, schema) for k in cfg.order_by]) if cfg.order_by else None

        def win(fn: exp.Expr, *, ordered: bool = True, spec: exp.WindowSpec | None = None) -> exp.Expr:
            return exp.Window(this=fn, partition_by=part or None, order=order if ordered else None, spec=spec)

        c = col(it.column) if it.column else None
        match it.fn:
            case "row_number":
                e: exp.Expr = win(exp.RowNumber())
            case "rank":
                e = win(exp.func("RANK"))
            case "dense_rank":
                e = win(exp.func("DENSE_RANK"))
            case "cumulative_sum":
                e = win(exp.Sum(this=c), spec=_rows(None, 0))
            case "cumulative_count":
                e = win(exp.Count(this=exp.Star()), spec=_rows(None, 0))
            case "previous":
                e = win(exp.func("LAG", c, lit(it.offset)))
            case "next":
                e = win(exp.func("LEAD", c, lit(it.offset)))
            case "pct_of_total":
                total = win(exp.Sum(this=c), ordered=False)
                e = exp.Div(
                    this=exp.Cast(this=c, to=exp.DataType.build("DOUBLE")),
                    expression=exp.Nullif(this=total, expression=lit(0)),
                )
            case "moving_avg":
                e = win(exp.Avg(this=c), spec=_rows(it.size - 1, 0))
            case "partition_agg":
                inner = agg_expr(Aggregation(column=it.column, fn=it.agg), schema)
                e = _over(inner, part)
        t = item_type(it, schema)
        if t is L.INTEGER:
            e = exp.Cast(this=e, to=exp.DataType.build("BIGINT"))
        elif t is L.DECIMAL and it.fn not in {"previous", "next"}:
            e = exp.Cast(this=e, to=exp.DataType.build("DOUBLE"))
        return e

    def compile(
        self, cfg: WindowConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        schema = schemas["in"]
        exprs: list[exp.Expr] = [col(c.name) for c in schema]
        exprs += [alias(self._expr(it, cfg, schema), it.output_name()) for it in cfg.items]
        return project(inputs["in"], exprs)


def _rows(preceding: int | None, following: int) -> exp.WindowSpec:
    start: exp.Expr | str = "UNBOUNDED" if preceding is None else lit(preceding)
    return exp.WindowSpec(
        kind="ROWS",
        start=start,
        start_side="PRECEDING",
        end="CURRENT ROW" if following == 0 else lit(following),
        end_side=None if following == 0 else "FOLLOWING",
    )


def _over(agg: exp.Expr, part: Sequence[exp.Expr]) -> exp.Expr:
    """Wrap the innermost aggregate (under casts/filters) in OVER (PARTITION BY …)."""
    if isinstance(agg, exp.Cast):
        return exp.Cast(this=_over(agg.this, part), to=agg.args["to"])
    return exp.Window(this=agg, partition_by=list(part) or None)
