from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error
from sowa.domain.schema import Column, Schema
from sowa.domain.types import LogicalType, unify
from sowa.nodes._conditions import ConditionBuilder, ConditionGroup
from sowa.nodes._values import Scalar, ValueError_, parse_bool, parse_number, typed_literal
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, lit, project
from sowa.nodes.registry import register_node

L = LogicalType


class Outcome(BaseModel):
    """What a rule produces: a fixed value or another column."""

    kind: Literal["value", "column"] = "value"
    value: Scalar = None
    column: str | None = None


class ConditionalRule(BaseModel):
    when: ConditionGroup = ConditionGroup()
    then: Outcome = Outcome()


class ConditionalConfig(NodeConfig):
    name: str = ""
    mode: Literal["new", "replace"] = "new"
    rules: list[ConditionalRule] = []
    otherwise: Outcome = Outcome()
    # Type of literal values; inferred (number/text/boolean) when null.
    value_type: LogicalType | None = None


def _literal_type(v: Scalar, locale: str) -> LogicalType | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return L.BOOLEAN
    if isinstance(v, int):
        return L.INTEGER
    if isinstance(v, float):
        return L.DECIMAL
    try:
        n = parse_number(v, locale)
    except ValueError_:
        return L.TEXT
    return L.INTEGER if isinstance(n, int) else L.DECIMAL


class _Typer:
    def __init__(self, cfg: ConditionalConfig, schema: Schema, ctx: NodeContext) -> None:
        self.cfg, self.schema, self.ctx = cfg, schema, ctx

    def outcomes(self) -> list[Outcome]:
        return [*(r.then for r in self.cfg.rules), self.cfg.otherwise]

    def type(self) -> LogicalType | None:
        """Common type of all outcomes; None when incompatible."""
        result: LogicalType | None = None
        literal_types = [_literal_type(o.value, self.ctx.locale) for o in self.outcomes() if o.kind == "value"]
        if self.cfg.value_type is not None:
            literal_types = [self.cfg.value_type if t is not None else None for t in literal_types]
        elif any(t is L.TEXT for t in literal_types):
            literal_types = [L.TEXT if t is not None else None for t in literal_types]
        column_types = [
            self.schema.type_of(o.column)
            for o in self.outcomes()
            if o.kind == "column" and o.column and self.schema.has(o.column)
        ]
        for t in [*literal_types, *column_types]:
            if t is None:
                continue
            if result is None:
                result = t
                continue
            u = unify(result, t)
            if u is None:
                return None
            result = u
        return result or L.TEXT

    def expr(self, o: Outcome, t: LogicalType) -> exp.Expr:
        if o.kind == "column" and o.column:
            return col(o.column)
        if o.value is None or o.value == "":
            return exp.Null() if t is not L.TEXT or o.value is None else lit("")
        if t in (L.INTEGER, L.DECIMAL):
            return lit(parse_number(o.value, self.ctx.locale))
        if t is L.BOOLEAN:
            return exp.Boolean(this=parse_bool(o.value))
        return typed_literal(o.value, t, self.ctx.locale) if t is not L.TEXT else lit(str(o.value))


@register_node
class ConditionalNode(NodeSpec[ConditionalConfig]):
    type = "conditional"
    config_model = ConditionalConfig
    label = "Coluna condicional"
    category = "columns"
    description = "Regras SE/SENÃO montadas visualmente, sem digitar fórmula."

    def validate(self, cfg: ConditionalConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        issues: list[Issue] = []
        if not cfg.name.strip():
            issues.append(error(IssueCode.EMPTY_NAME, "Dê um nome para a coluna."))
        elif cfg.mode == "new" and schema.has(cfg.name):
            issues.append(
                error(
                    IssueCode.DUPLICATE_COLUMN,
                    f'Já existe uma coluna "{cfg.name}".',
                    column=cfg.name,
                    hint='Escolha outro nome ou use "substituir coluna".',
                )
            )
        elif cfg.mode == "replace" and not schema.has(cfg.name):
            issues.append(column_not_found(cfg.name, where=ctx.input_labels.get("in")))
        if not cfg.rules:
            issues.append(error(IssueCode.INVALID_CONFIG, "Adicione pelo menos uma regra SE."))
        b = ConditionBuilder(schema, ctx)
        for i, r in enumerate(cfg.rules, start=1):
            if not r.when.conditions:
                issues.append(error(IssueCode.INVALID_CONFIG, f"A regra {i} não tem condição."))
            b.group(r.when)
        issues.extend(b.issues)
        t = _Typer(cfg, schema, ctx)
        for o in t.outcomes():
            if o.kind == "column" and o.column and not schema.has(o.column):
                issues.append(column_not_found(o.column, where=ctx.input_labels.get("in")))
        if not issues and t.type() is None:
            issues.append(
                error(
                    IssueCode.TYPE_MISMATCH,
                    "Os resultados das regras têm tipos diferentes (ex.: número e texto).",
                    hint="Use valores do mesmo tipo em todas as regras.",
                )
            )
        return issues

    def infer_schema(self, cfg: ConditionalConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        schema = inputs["in"]
        t = _Typer(cfg, schema, ctx).type() or L.TEXT
        if cfg.mode == "replace":
            return Schema(columns=[Column(name=c.name, type=t if c.name == cfg.name else c.type) for c in schema])
        return Schema(columns=[*schema.columns, Column(name=cfg.name, type=t)])

    def compile(
        self, cfg: ConditionalConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        schema = schemas["in"]
        typer = _Typer(cfg, schema, ctx)
        t = typer.type() or L.TEXT
        b = ConditionBuilder(schema, ctx)
        case = exp.Case()
        for r in cfg.rules:
            cond = b.group(r.when)
            if cond is not None:
                case = case.when(cond, typer.expr(r.then, t))
        e = case.else_(typer.expr(cfg.otherwise, t))
        exprs: list[exp.Expr] = [
            alias(e, c.name) if cfg.mode == "replace" and c.name == cfg.name else col(c.name) for c in schema
        ]
        if cfg.mode == "new":
            exprs.append(alias(e, cfg.name))
        return project(inputs["in"], exprs)
