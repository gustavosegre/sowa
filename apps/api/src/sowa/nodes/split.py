from __future__ import annotations

import re
from typing import Literal

from pydantic import Field
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error
from sowa.domain.schema import Column, Schema
from sowa.domain.types import LogicalType, label
from sowa.formula.functions import tmpl
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, lit, project
from sowa.nodes.registry import register_node

L = LogicalType


class SplitConfig(NodeConfig):
    column: str = ""
    # delimiter: "Texto para colunas" · position: fixed widths · regex: capture groups
    mode: Literal["delimiter", "position", "regex"] = "delimiter"
    delimiter: str = ";"
    positions: list[int] = []  # cut points (1-based character positions where a new part starts)
    pattern: str = ""
    parts: int = Field(default=2, ge=1, le=50)
    names: list[str] = []
    keep_original: bool = True
    trim: bool = True


def part_names(cfg: SplitConfig) -> list[str]:
    n = len(cfg.positions) + 1 if cfg.mode == "position" else cfg.parts
    return [cfg.names[i] if i < len(cfg.names) and cfg.names[i].strip() else f"{cfg.column}_{i + 1}" for i in range(n)]


@register_node
class SplitNode(NodeSpec[SplitConfig]):
    type = "split"
    config_model = SplitConfig
    label = "Dividir coluna"
    category = "columns"
    description = "Por delimitador, posição ou expressão regular (Texto para colunas)."

    def validate(self, cfg: SplitConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        if not cfg.column:
            return [error(IssueCode.INVALID_CONFIG, "Escolha a coluna a dividir.")]
        c = schema.get(cfg.column)
        if c is None:
            return [column_not_found(cfg.column, where=ctx.input_labels.get("in"))]
        issues: list[Issue] = []
        if c.type is not L.TEXT:
            issues.append(error(IssueCode.TYPE_MISMATCH, f'"{cfg.column}" é {label(c.type)}; divida colunas de Texto.'))
        if cfg.mode == "delimiter" and not cfg.delimiter:
            issues.append(error(IssueCode.INVALID_CONFIG, "Informe o delimitador."))
        if cfg.mode == "position" and (not cfg.positions or sorted(cfg.positions) != cfg.positions):
            issues.append(error(IssueCode.INVALID_CONFIG, "Informe as posições de corte em ordem crescente."))
        if cfg.mode == "regex":
            try:
                groups = re.compile(cfg.pattern).groups
                if groups < 1:
                    issues.append(
                        error(
                            IssueCode.INVALID_CONFIG,
                            "A expressão regular precisa de grupos de captura, ex.: (\\d+)-(\\d+).",
                        )
                    )
            except re.error as e:
                issues.append(error(IssueCode.INVALID_CONFIG, f"Expressão regular inválida: {e}."))
        existing = {c.name for c in schema if cfg.keep_original or c.name != cfg.column}
        for n in part_names(cfg):
            if n in existing:
                issues.append(error(IssueCode.DUPLICATE_COLUMN, f'Já existe uma coluna "{n}".', column=n))
        return issues

    def infer_schema(self, cfg: SplitConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        base = [c for c in inputs["in"] if cfg.keep_original or c.name != cfg.column]
        return Schema(columns=[*base, *(Column(name=n, type=L.TEXT) for n in part_names(cfg))])

    def compile(
        self, cfg: SplitConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        ref = col(cfg.column)
        names = part_names(cfg)
        parts: list[exp.Expr] = []
        if cfg.mode == "delimiter":
            for i in range(len(names)):
                if i == len(names) - 1:
                    # The last part keeps the rest of the text (like Excel with a column limit).
                    parts.append(
                        tmpl(
                            "NULLIF(ARRAY_TO_STRING(STRING_SPLIT(_0, _1)[_2:], _1), '')",
                            ref,
                            lit(cfg.delimiter),
                            lit(i + 1),
                        )
                    )
                else:
                    parts.append(tmpl("STRING_SPLIT(_0, _1)[_2]", ref, lit(cfg.delimiter), lit(i + 1)))
        elif cfg.mode == "position":
            cuts = [1, *cfg.positions]
            for i, start in enumerate(cuts):
                if i + 1 < len(cuts):
                    parts.append(exp.Substring(this=ref.copy(), start=lit(start), length=lit(cuts[i + 1] - start)))
                else:
                    parts.append(exp.Substring(this=ref.copy(), start=lit(start)))
        else:
            for i in range(len(names)):
                parts.append(tmpl("NULLIF(REGEXP_EXTRACT(_0, _1, _2), '')", ref, lit(cfg.pattern), lit(i + 1)))
        if cfg.trim:
            parts = [exp.func("TRIM", p) for p in parts]
        exprs: list[exp.Expr] = [col(c.name) for c in schemas["in"] if cfg.keep_original or c.name != cfg.column]
        exprs += [alias(p, n) for p, n in zip(parts, names, strict=True)]
        return project(inputs["in"], exprs)
