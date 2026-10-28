from __future__ import annotations

from typing import Literal

from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error
from forja.domain.schema import Column, Schema
from forja.domain.types import TEMPORAL_TYPES, LogicalType, label
from forja.formula.functions import tmpl
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, project
from forja.nodes.registry import register_node

L = LogicalType

Part = Literal[
    "year", "quarter", "month", "month_name", "year_month", "week", "weekday", "weekday_name", "day", "hour", "date"
]

PART_LABELS: dict[str, str] = {
    "year": "ano",
    "quarter": "trimestre",
    "month": "mes",
    "month_name": "nome_mes",
    "year_month": "ano_mes",
    "week": "semana",
    "weekday": "dia_semana",
    "weekday_name": "nome_dia_semana",
    "day": "dia",
    "hour": "hora",
    "date": "data",
}

MONTHS = (
    "['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', "
    "'novembro', 'dezembro']"
)
WEEKDAYS = "['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']"

_SQL: dict[str, tuple[str, LogicalType]] = {
    "year": ("YEAR(_0)", L.INTEGER),
    "quarter": ("QUARTER(_0)", L.INTEGER),
    "month": ("MONTH(_0)", L.INTEGER),
    "month_name": (f"LIST_EXTRACT({MONTHS}, MONTH(_0))", L.TEXT),
    "year_month": ("STRFTIME(CAST(_0 AS DATE), '%Y-%m')", L.TEXT),
    "week": ("WEEKOFYEAR(_0)", L.INTEGER),
    # 1 = segunda … 7 = domingo (ISO), the Brazilian business convention.
    "weekday": ("ISODOW(_0)", L.INTEGER),
    "weekday_name": (f"LIST_EXTRACT({WEEKDAYS}, ISODOW(_0))", L.TEXT),
    "day": ("DAY(_0)", L.INTEGER),
    "hour": ("HOUR(_0)", L.INTEGER),
    "date": ("CAST(_0 AS DATE)", L.DATE),
}


class DatePartsConfig(NodeConfig):
    column: str = ""
    parts: list[Part] = ["year", "month"]
    prefix: str | None = None  # default: "<column>_"


def output_name(cfg: DatePartsConfig, part: str) -> str:
    prefix = cfg.prefix if cfg.prefix is not None else f"{cfg.column}_"
    return f"{prefix}{PART_LABELS[part]}"


@register_node
class DatePartsNode(NodeSpec[DatePartsConfig]):
    type = "date_parts"
    config_model = DatePartsConfig
    label = "Extrair de data"
    category = "columns"
    description = "Ano, trimestre, mês, semana, dia da semana e nomes em pt-BR."

    def validate(self, cfg: DatePartsConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        if not cfg.column:
            return [error(IssueCode.INVALID_CONFIG, "Escolha a coluna de data.")]
        c = schema.get(cfg.column)
        if c is None:
            return [column_not_found(cfg.column, where=ctx.input_labels.get("in"))]
        issues: list[Issue] = []
        if c.type not in TEMPORAL_TYPES:
            issues.append(
                error(
                    IssueCode.TYPE_MISMATCH,
                    f'"{cfg.column}" é {label(c.type)}, não uma data.',
                    column=cfg.column,
                    hint='Converta a coluna para Data com "Alterar tipo".',
                )
            )
        if c.type is L.DATE and "hour" in cfg.parts:
            issues.append(error(IssueCode.TYPE_MISMATCH, "Uma Data não tem hora.", column=cfg.column))
        if not cfg.parts:
            issues.append(error(IssueCode.INVALID_CONFIG, "Escolha pelo menos uma parte da data."))
        for p in cfg.parts:
            if schema.has(output_name(cfg, p)):
                issues.append(
                    error(
                        IssueCode.DUPLICATE_COLUMN,
                        f'Já existe uma coluna "{output_name(cfg, p)}".',
                        column=output_name(cfg, p),
                        hint="Mude o prefixo.",
                    )
                )
        return issues

    def infer_schema(self, cfg: DatePartsConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        extra = [Column(name=output_name(cfg, p), type=_SQL[p][1]) for p in cfg.parts]
        return Schema(columns=[*inputs["in"].columns, *extra])

    def compile(
        self, cfg: DatePartsConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        exprs: list[exp.Expr] = [col(c.name) for c in schemas["in"]]
        for p in cfg.parts:
            sql, t = _SQL[p]
            e = tmpl(sql, col(cfg.column))
            if t is L.INTEGER:
                e = exp.Cast(this=e, to=exp.DataType.build("BIGINT"))
            exprs.append(alias(e, output_name(cfg, p)))
        return project(inputs["in"], exprs)
