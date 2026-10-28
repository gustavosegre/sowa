from __future__ import annotations

from typing import Literal

from sqlglot import exp

from forja.domain.issues import Issue, column_not_found
from forja.domain.schema import Schema
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, col, from_input
from forja.nodes.registry import register_node
from forja.nodes.sort import SortKey, order_expr


class DistinctConfig(NodeConfig):
    # Empty keys = whole row.
    keys: list[str] = []
    keep: Literal["first", "last"] = "first"
    order_by: list[SortKey] = []


@register_node
class DistinctNode(NodeSpec[DistinctConfig]):
    type = "distinct"
    config_model = DistinctConfig
    label = "Remover duplicatas"
    category = "rows"
    description = "Linha inteira ou por chaves, mantendo a primeira ou a última por ordenação."
    cacheable = True

    def validate(self, cfg: DistinctConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        where = ctx.input_labels.get("in")
        names = [*cfg.keys, *(k.column for k in cfg.order_by)]
        return [column_not_found(n, where=where) for n in names if not schema.has(n)]

    def compile(
        self, cfg: DistinctConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        if not cfg.keys:
            return exp.select(exp.Star()).distinct().from_(from_input(inputs["in"]))
        order = [order_expr(k, schemas["in"]) for k in cfg.order_by]
        if cfg.keep == "last":
            for o in order:
                o.set("desc", not o.args.get("desc"))
                o.set("nulls_first", not o.args.get("nulls_first"))
        rn = exp.Window(
            this=exp.RowNumber(),
            partition_by=[col(k) for k in cfg.keys],
            order=exp.Order(expressions=order) if order else None,
        )
        sel = exp.select(exp.Star()).from_(from_input(inputs["in"]))
        return sel.qualify(exp.EQ(this=rn, expression=exp.Literal.number(1)))
