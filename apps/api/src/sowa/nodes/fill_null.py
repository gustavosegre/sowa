from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error
from sowa.domain.schema import Schema
from sowa.domain.types import NUMERIC_TYPES, LogicalType, label
from sowa.formula.functions import tmpl
from sowa.nodes._values import Scalar, ValueError_, typed_literal, value_error_message
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, from_input
from sowa.nodes.registry import register_node
from sowa.nodes.sort import SortKey, order_expr

L = LogicalType
ROW = "__sowa_row"


class FillRule(BaseModel):
    column: str
    # value: fixed value · previous: "preencher para baixo" · next: para cima · mean/median: of the column
    method: Literal["value", "previous", "next", "mean", "median"] = "value"
    value: Scalar = None


class FillNullConfig(NodeConfig):
    rules: list[FillRule] = []
    # Row order for previous/next. Empty = order of the rows as they arrive.
    order_by: list[SortKey] = []


@register_node
class FillNullNode(NodeSpec[FillNullConfig]):
    type = "fill_null"
    config_model = FillNullConfig
    label = "Preencher vazios"
    category = "columns"
    description = "Valor fixo, anterior/próximo (preencher para baixo) ou média."

    def validate(self, cfg: FillNullConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        where = ctx.input_labels.get("in")
        issues: list[Issue] = [
            column_not_found(k.column, where=where) for k in cfg.order_by if not schema.has(k.column)
        ]
        for r in cfg.rules:
            c = schema.get(r.column)
            if c is None:
                issues.append(column_not_found(r.column, where=where))
                continue
            if r.method in ("mean", "median") and c.type not in NUMERIC_TYPES:
                issues.append(
                    error(
                        IssueCode.TYPE_MISMATCH,
                        f'Média/mediana precisa de números, mas "{r.column}" é {label(c.type)}.',
                        column=r.column,
                    )
                )
            if r.method == "value":
                if r.value is None:
                    issues.append(
                        error(
                            IssueCode.INVALID_CONFIG, f'Informe o valor para preencher "{r.column}".', column=r.column
                        )
                    )
                else:
                    try:
                        typed_literal(r.value, c.type, ctx.locale)
                    except ValueError_ as e:
                        issues.append(
                            error(
                                IssueCode.TYPE_MISMATCH,
                                value_error_message(r.column, r.value, c.type, str(e)),
                                column=r.column,
                            )
                        )
        return issues

    def infer_schema(self, cfg: FillNullConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        schema = inputs["in"]
        rules = {r.column: r for r in cfg.rules}
        cols = []
        for c in schema:
            r = rules.get(c.name)
            # The mean of integers is fractional.
            t = L.DECIMAL if r is not None and r.method in ("mean", "median") else c.type
            cols.append(c.model_copy(update={"type": t}))
        return Schema(columns=cols)

    def compile(
        self, cfg: FillNullConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        schema = schemas["in"]
        rules = {r.column: r for r in cfg.rules}
        directional = any(r.method in ("previous", "next") for r in cfg.rules)
        src = from_input(inputs["in"])
        if directional and not cfg.order_by:
            # Number the rows in arrival order so "previous" and "next" are well defined.
            numbered = exp.select(exp.Star(), alias(exp.Window(this=exp.RowNumber()), ROW)).from_(src)
            src = exp.Subquery(this=numbered, alias=exp.TableAlias(this=exp.to_identifier("__numbered")))
        order = (
            [order_expr(k, schema) for k in cfg.order_by]
            if cfg.order_by
            else [exp.Ordered(this=col(ROW), nulls_first=False)]
        )
        exprs: list[exp.Expr] = []
        for c in schema:
            r = rules.get(c.name)
            ref: exp.Expr = col(c.name)
            if r is None:
                exprs.append(ref)
                continue
            fill: exp.Expr
            if r.method == "value":
                fill = typed_literal(r.value, c.type, ctx.locale)
            elif r.method in ("mean", "median"):
                agg = "AVG" if r.method == "mean" else "MEDIAN"
                fill = exp.Window(this=exp.func(agg, exp.Cast(this=ref.copy(), to=exp.DataType.build("DOUBLE"))))
                ref = exp.Cast(this=ref, to=exp.DataType.build("DOUBLE"))
            else:
                frame = (
                    "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
                    if r.method == "previous"
                    else "ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING"
                )
                fn = "LAST_VALUE" if r.method == "previous" else "FIRST_VALUE"
                w = tmpl(f"{fn}(_0 IGNORE NULLS) OVER (ORDER BY _1 {frame})", ref.copy(), exp.column("__placeholder__"))
                window = w if isinstance(w, exp.Window) else None
                assert window is not None
                window.set("order", exp.Order(expressions=[o.copy() for o in order]))
                fill = window
            exprs.append(alias(exp.Coalesce(this=ref, expressions=[fill]), c.name))
        return exp.select(*exprs).from_(src)
