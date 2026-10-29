from __future__ import annotations

from pydantic import BaseModel
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error
from sowa.domain.schema import Column, Schema
from sowa.formula.parser import Locale
from sowa.formula.service import CompiledFormula, compile_formula, formula_issue
from sowa.formula.typecheck import FormulaError
from sowa.nodes._aggs import Aggregation, agg_expr, agg_type, validate_agg
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, from_input
from sowa.nodes.registry import register_node


class Measure(BaseModel):
    """Calculated measure: a formula in aggregate context, e.g. SOMA([receita]) / SOMA([qtd])."""

    name: str
    formula: str


class GroupByConfig(NodeConfig):
    keys: list[str] = []
    aggs: list[Aggregation] = []
    measures: list[Measure] = []


def compile_measure(m: Measure, schema: Schema, keys: list[str], ctx: NodeContext) -> CompiledFormula:
    locale: Locale = "en-US" if ctx.locale == "en-US" else "pt-BR"
    return compile_formula(m.formula, schema, locale=locale, context="aggregate", group_keys=keys, params=ctx.params)


def output_names(cfg: GroupByConfig) -> list[str]:
    return [*cfg.keys, *(a.output_name() for a in cfg.aggs), *(m.name for m in cfg.measures)]


@register_node
class GroupByNode(NodeSpec[GroupByConfig]):
    type = "group_by"
    config_model = GroupByConfig
    label = "Agrupar"
    category = "aggregate"
    description = "Agrupa linhas por chaves e calcula agregações e medidas."
    cacheable = True

    def validate(self, cfg: GroupByConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        where = ctx.input_labels.get("in")
        issues: list[Issue] = [column_not_found(k, where=where) for k in cfg.keys if not schema.has(k)]
        for a in cfg.aggs:
            issues.extend(validate_agg(a, schema, where))
        for m in cfg.measures:
            if not m.name.strip():
                issues.append(error(IssueCode.EMPTY_NAME, "Dê um nome para a medida calculada."))
            try:
                compile_measure(m, schema, cfg.keys, ctx)
            except FormulaError as e:
                issues.append(formula_issue(e, field_label=f'medida "{m.name}"'))
        if not cfg.keys and not cfg.aggs and not cfg.measures:
            issues.append(
                error(
                    IssueCode.INVALID_CONFIG,
                    "Escolha as colunas para agrupar e as agregações.",
                    hint='Ex.: agrupar por "uf" e somar "receita".',
                )
            )
        seen: set[str] = set()
        for n in output_names(cfg):
            if n in seen:
                issues.append(
                    error(
                        IssueCode.DUPLICATE_COLUMN,
                        f'Duas colunas de saída se chamam "{n}".',
                        column=n,
                        hint="Dê nomes diferentes às agregações.",
                    )
                )
            seen.add(n)
        return issues

    def infer_schema(self, cfg: GroupByConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        schema = inputs["in"]
        cols = [Column(name=k, type=schema.type_of(k)) for k in cfg.keys]
        cols += [Column(name=a.output_name(), type=agg_type(a, schema)) for a in cfg.aggs]
        cols += [Column(name=m.name, type=compile_measure(m, schema, cfg.keys, ctx).type) for m in cfg.measures]
        return Schema(columns=cols)

    def compile(
        self, cfg: GroupByConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        schema = schemas["in"]
        exprs: list[exp.Expr] = [col(k) for k in cfg.keys]
        exprs += [alias(agg_expr(a, schema), a.output_name()) for a in cfg.aggs]
        exprs += [alias(compile_measure(m, schema, cfg.keys, ctx).sql, m.name) for m in cfg.measures]
        sel = exp.select(*exprs).from_(from_input(inputs["in"]))
        if cfg.keys:
            sel = sel.group_by(*[col(k) for k in cfg.keys])
        return sel
