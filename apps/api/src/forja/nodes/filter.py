from __future__ import annotations

from typing import Literal

from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, error
from forja.domain.schema import Schema
from forja.domain.types import LogicalType, label
from forja.formula.service import compile_formula, formula_issue
from forja.formula.typecheck import FormulaError
from forja.nodes._conditions import Condition, ConditionBuilder, ConditionGroup, locale_of
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec
from forja.nodes.registry import register_node

L = LogicalType

__all__ = ["Condition", "ConditionGroup", "FilterConfig", "FilterNode"]


class FilterConfig(NodeConfig):
    mode: Literal["rules", "formula"] = "rules"
    rules: ConditionGroup = ConditionGroup()
    formula: str = ""


@register_node
class FilterNode(NodeSpec[FilterConfig]):
    type = "filter"
    config_model = FilterConfig
    label = "Filtrar"
    category = "rows"
    description = "Mantém só as linhas que atendem às condições."

    def _condition(self, cfg: FilterConfig, schema: Schema, ctx: NodeContext) -> tuple[exp.Expr | None, list[Issue]]:
        if cfg.mode == "formula":
            if not cfg.formula.strip():
                return None, []
            try:
                f = compile_formula(cfg.formula, schema, locale=locale_of(ctx))
            except FormulaError as e:
                return None, [formula_issue(e)]
            if f.type is not L.BOOLEAN:
                return None, [
                    error(
                        IssueCode.FORMULA_TYPE,
                        f"A fórmula do filtro precisa resultar em verdadeiro/falso, mas resulta em {label(f.type)}.",
                        hint="Use uma comparação, ex.: [valor] > 100",
                    )
                ]
            return f.sql, []
        b = ConditionBuilder(schema, ctx)
        cond = b.group(cfg.rules)
        return cond, b.issues

    def validate(self, cfg: FilterConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        return self._condition(cfg, inputs["in"], ctx)[1]

    def compile(
        self, cfg: FilterConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        cond, _ = self._condition(cfg, schemas["in"], ctx)
        sel = inputs["in"].copy()
        return sel.where(cond) if cond is not None else sel
