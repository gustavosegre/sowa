from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel
from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error
from forja.domain.schema import Schema
from forja.domain.types import LogicalType, label
from forja.nodes._values import Scalar, ValueError_, typed_literal, value_error_message
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, lit, project
from forja.nodes.registry import register_node

L = LogicalType


class ReplaceRule(BaseModel):
    find: Scalar = None  # None in "exact" mode means "empty cell"
    replace: Scalar = None


class ReplaceConfig(NodeConfig):
    column: str = ""
    # exact: from/para table (whole cell) · contains: replace a piece of text · regex: regular expression
    mode: Literal["exact", "contains", "regex"] = "exact"
    rules: list[ReplaceRule] = []
    case_sensitive: bool = True


def _issues(cfg: ReplaceConfig, schema: Schema, ctx: NodeContext) -> list[Issue]:
    c = schema.get(cfg.column)
    if not cfg.column:
        return [error(IssueCode.INVALID_CONFIG, "Escolha a coluna onde substituir valores.")]
    if c is None:
        return [column_not_found(cfg.column, where=ctx.input_labels.get("in"))]
    issues: list[Issue] = []
    if cfg.mode != "exact" and c.type is not L.TEXT:
        issues.append(
            error(
                IssueCode.TYPE_MISMATCH,
                f'Substituir trechos só funciona com Texto, e "{cfg.column}" é {label(c.type)}.',
                column=cfg.column,
                hint='Use o modo "valor exato" ou converta a coluna para Texto.',
            )
        )
    for r in cfg.rules:
        for raw in (r.find, r.replace):
            if cfg.mode == "exact" and raw is not None and c.type is not L.TEXT:
                try:
                    typed_literal(raw, c.type, ctx.locale)
                except ValueError_ as e:
                    issues.append(
                        error(
                            IssueCode.TYPE_MISMATCH,
                            value_error_message(cfg.column, raw, c.type, str(e)),
                            column=cfg.column,
                        )
                    )
        if cfg.mode == "regex" and isinstance(r.find, str):
            try:
                re.compile(r.find)
            except re.error as e:
                issues.append(
                    error(IssueCode.INVALID_CONFIG, f'Expressão regular inválida "{r.find}": {e}.', column=cfg.column)
                )
    return issues


@register_node
class ReplaceNode(NodeSpec[ReplaceConfig]):
    type = "replace"
    config_model = ReplaceConfig
    label = "Substituir valores"
    category = "columns"
    description = "Tabela de/para, trecho de texto ou expressão regular."

    def validate(self, cfg: ReplaceConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        return _issues(cfg, inputs["in"], ctx)

    def compile(
        self, cfg: ReplaceConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        schema = schemas["in"]
        t = schema.type_of(cfg.column)
        ref: exp.Expr = col(cfg.column)
        new: exp.Expr
        if cfg.mode == "exact":
            case = exp.Case()
            for r in cfg.rules:
                target = typed_literal(r.replace, t, ctx.locale) if r.replace is not None else exp.Null()
                if r.find is None or r.find == "":
                    cond: exp.Expr = exp.Is(this=col(cfg.column), expression=exp.Null())
                    if t is L.TEXT:
                        cond = exp.or_(cond, exp.EQ(this=col(cfg.column), expression=lit("")))
                else:
                    find = typed_literal(r.find, t, ctx.locale)
                    left: exp.Expr = col(cfg.column)
                    if t is L.TEXT and not cfg.case_sensitive and isinstance(r.find, str):
                        left, find = exp.Lower(this=left), lit(r.find.lower())
                    cond = exp.EQ(this=left, expression=find)
                case = case.when(cond, target)
            new = case.else_(col(cfg.column)) if cfg.rules else col(cfg.column)
        else:
            new = ref
            for r in cfg.rules:
                needle, to = str(r.find or ""), str(r.replace or "")
                if not needle:
                    continue
                if cfg.mode == "contains" and cfg.case_sensitive:
                    new = exp.func("REPLACE", new, lit(needle), lit(to))
                else:
                    pattern = needle if cfg.mode == "regex" else re.escape(needle)
                    flags = "g" if cfg.case_sensitive else "gi"
                    new = exp.func("REGEXP_REPLACE", new, lit(pattern), lit(to), lit(flags))
        return project(inputs["in"], [alias(new, c.name) if c.name == cfg.column else col(c.name) for c in schema])
