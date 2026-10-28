from __future__ import annotations

from typing import Literal

from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error
from forja.domain.schema import Schema
from forja.domain.types import LogicalType, label
from forja.formula.functions import tmpl
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, project
from forja.nodes.registry import register_node

_PROPER = "ARRAY_TO_STRING(LIST_TRANSFORM(STR_SPLIT(LOWER(_0), ' '), LAMBDA w : UPPER(w[1]) || w[2:]), ' ')"


class TextCleanConfig(NodeConfig):
    columns: list[str] = []
    trim: bool = True
    collapse_spaces: bool = True
    case: Literal["none", "upper", "lower", "title"] = "none"
    remove_accents: bool = False
    empty_as_null: bool = False


def clean_expr(e: exp.Expr, cfg: TextCleanConfig) -> exp.Expr:
    if cfg.collapse_spaces:
        e = tmpl("REGEXP_REPLACE(_0, '\\s+', ' ', 'g')", e)
    if cfg.trim:
        e = exp.func("TRIM", e)
    if cfg.remove_accents:
        e = exp.func("STRIP_ACCENTS", e)
    if cfg.case == "upper":
        e = exp.Upper(this=e)
    elif cfg.case == "lower":
        e = exp.Lower(this=e)
    elif cfg.case == "title":
        e = tmpl(_PROPER, e)
    if cfg.empty_as_null:
        e = exp.Nullif(this=e, expression=exp.Literal.string(""))
    return e


@register_node
class TextCleanNode(NodeSpec[TextCleanConfig]):
    type = "text_clean"
    config_model = TextCleanConfig
    label = "Limpar texto"
    category = "columns"
    description = "Aparar espaços, maiúsculas/minúsculas, remover acentos e espaços duplos."

    def validate(self, cfg: TextCleanConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        issues: list[Issue] = []
        if not cfg.columns:
            issues.append(error(IssueCode.INVALID_CONFIG, "Escolha as colunas de texto para limpar."))
        for name in cfg.columns:
            c = schema.get(name)
            if c is None:
                issues.append(column_not_found(name, where=ctx.input_labels.get("in")))
            elif c.type is not LogicalType.TEXT:
                issues.append(
                    error(
                        IssueCode.TYPE_MISMATCH,
                        f'"{name}" é {label(c.type)}; "Limpar texto" só funciona com Texto.',
                        column=name,
                        hint='Converta a coluna para Texto com "Alterar tipo".',
                    )
                )
        return issues

    def compile(
        self, cfg: TextCleanConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        targets = set(cfg.columns)
        return project(
            inputs["in"],
            [alias(clean_expr(col(c.name), cfg), c.name) if c.name in targets else col(c.name) for c in schemas["in"]],
        )
