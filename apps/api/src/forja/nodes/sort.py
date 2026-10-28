from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error
from forja.domain.schema import Schema
from forja.domain.types import LogicalType
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, col
from forja.nodes.registry import register_node


class SortKey(BaseModel):
    column: str
    direction: Literal["asc", "desc"] = "asc"
    nulls: Literal["first", "last"] = "last"
    case_sensitive: bool = False


class SortConfig(NodeConfig):
    keys: list[SortKey] = []


def order_expr(k: SortKey, schema: Schema) -> exp.Ordered:
    ref: exp.Expr = col(k.column)
    c = schema.get(k.column)
    if c is not None and c.type is LogicalType.TEXT and not k.case_sensitive:
        ref = exp.Collate(this=ref, expression=exp.var("NOCASE"))
    return exp.Ordered(this=ref, desc=k.direction == "desc", nulls_first=k.nulls == "first")


@register_node
class SortNode(NodeSpec[SortConfig]):
    type = "sort"
    config_model = SortConfig
    label = "Ordenar"
    category = "rows"
    description = "Ordena as linhas por uma ou mais colunas."

    def validate(self, cfg: SortConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        issues = [
            column_not_found(k.column, where=ctx.input_labels.get("in"))
            for k in cfg.keys
            if not inputs["in"].has(k.column)
        ]
        if not cfg.keys:
            issues.append(error(IssueCode.INVALID_CONFIG, "Escolha pelo menos uma coluna para ordenar."))
        return issues

    def compile(
        self, cfg: SortConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        return inputs["in"].copy().order_by(*[order_expr(k, schemas["in"]) for k in cfg.keys])
