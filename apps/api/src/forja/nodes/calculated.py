from __future__ import annotations

from typing import Literal

from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, error, plural, warning
from forja.domain.schema import Column, Schema
from forja.formula.parser import Locale
from forja.formula.service import CompiledFormula, compile_formula, formula_issue
from forja.formula.typecheck import FormulaError
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, QueryRunner, alias, col, count_star, lit, project
from forja.nodes.registry import register_node


class CalculatedConfig(NodeConfig):
    name: str = ""
    mode: Literal["new", "replace"] = "new"
    formula: str = ""


def _compile(cfg: CalculatedConfig, schema: Schema, ctx: NodeContext) -> CompiledFormula:
    locale: Locale = "en-US" if ctx.locale == "en-US" else "pt-BR"
    return compile_formula(cfg.formula, schema, locale=locale)


@register_node
class CalculatedNode(NodeSpec[CalculatedConfig]):
    type = "calculated"
    config_model = CalculatedConfig
    label = "Coluna calculada"
    category = "columns"
    description = "Cria ou substitui uma coluna usando uma fórmula."

    def validate(self, cfg: CalculatedConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        issues: list[Issue] = []
        if not cfg.name.strip():
            issues.append(error(IssueCode.EMPTY_NAME, "Dê um nome para a coluna calculada."))
        elif cfg.mode == "new" and schema.has(cfg.name):
            issues.append(
                error(
                    IssueCode.DUPLICATE_COLUMN,
                    f'Já existe uma coluna "{cfg.name}".',
                    column=cfg.name,
                    hint='Escolha outro nome ou use o modo "substituir coluna".',
                )
            )
        elif cfg.mode == "replace" and not schema.has(cfg.name):
            issues.append(
                error(
                    IssueCode.COLUMN_NOT_FOUND,
                    f'A coluna "{cfg.name}" não existe para ser substituída.',
                    column=cfg.name,
                )
            )
        if not cfg.formula.strip():
            issues.append(
                error(IssueCode.FORMULA_SYNTAX, "Escreva a fórmula da coluna.", hint="Ex.: [preço] * [quantidade]")
            )
            return issues
        try:
            _compile(cfg, schema, ctx)
        except FormulaError as e:
            issues.append(formula_issue(e))
        return issues

    def infer_schema(self, cfg: CalculatedConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        schema = inputs["in"]
        t = _compile(cfg, schema, ctx).type
        if cfg.mode == "replace":
            return Schema(columns=[Column(name=c.name, type=t if c.name == cfg.name else c.type) for c in schema])
        return Schema(columns=[*schema.columns, Column(name=cfg.name, type=t)])

    def compile(
        self, cfg: CalculatedConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        schema = schemas["in"]
        expr = _compile(cfg, schema, ctx).sql
        exprs: list[exp.Expr] = [
            alias(expr, c.name) if cfg.mode == "replace" and c.name == cfg.name else col(c.name) for c in schema
        ]
        if cfg.mode == "new":
            exprs.append(alias(expr, cfg.name))
        return project(inputs["in"], exprs)

    def runtime_issues(
        self,
        cfg: CalculatedConfig,
        inputs: dict[str, exp.Select],
        output: exp.Select,
        schemas: dict[str, Schema],
        ctx: NodeContext,
        run: QueryRunner,
    ) -> list[Issue]:
        guards = _compile(cfg, schemas["in"], ctx).div_guards
        if not guards:
            return []
        cond = exp.or_(*[exp.EQ(this=g.copy(), expression=lit(0)) for g in guards])
        n = run(project(inputs["in"], [exp.Filter(this=count_star(), expression=exp.Where(this=cond))]))[0][0]
        if not n:
            return []
        return [
            warning(
                IssueCode.DIVISION_BY_ZERO,
                f'Divisão por zero em {plural(int(n), "linha", "linhas")} de "{cfg.name}". O resultado ficou vazio.',
                column=cfg.name,
                count=int(n),
                hint="Use SEERRO(...; 0) para trocar o vazio por outro valor.",
            )
        ]
