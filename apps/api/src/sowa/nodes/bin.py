from __future__ import annotations

import itertools
from typing import Literal

from pydantic import Field
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error
from sowa.domain.schema import Column, Schema
from sowa.domain.types import NUMERIC_TYPES, LogicalType, label
from sowa.formula.functions import tmpl
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, lit, project
from sowa.nodes.registry import register_node

L = LogicalType


class BinConfig(NodeConfig):
    column: str = ""
    name: str = ""  # default "<column>_faixa"
    mode: Literal["manual", "equal"] = "manual"
    # manual: sorted limits; [100, 500] -> "< 100", "100 a 500", "≥ 500"
    boundaries: list[float] = []
    labels: list[str] = []  # optional, one per range
    count: int = Field(default=5, ge=2, le=100)


def _fmt(v: float) -> str:
    s = f"{v:,.10g}" if not float(v).is_integer() else f"{int(v):,}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def manual_labels(cfg: BinConfig) -> list[str]:
    b = cfg.boundaries
    if not b:
        return []
    out = [f"< {_fmt(b[0])}"]
    out += [f"{_fmt(lo)} a {_fmt(hi)}" for lo, hi in itertools.pairwise(b)]
    out.append(f"≥ {_fmt(b[-1])}")
    return [cfg.labels[i] if i < len(cfg.labels) and cfg.labels[i].strip() else x for i, x in enumerate(out)]


def out_name(cfg: BinConfig) -> str:
    return cfg.name.strip() or f"{cfg.column}_faixa"


@register_node
class BinNode(NodeSpec[BinConfig]):
    type = "bin"
    config_model = BinConfig
    label = "Faixas"
    category = "columns"
    description = "Agrupa números em faixas (limites manuais ou intervalos iguais)."

    def validate(self, cfg: BinConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        if not cfg.column:
            return [error(IssueCode.INVALID_CONFIG, "Escolha a coluna numérica.")]
        c = schema.get(cfg.column)
        if c is None:
            return [column_not_found(cfg.column, where=ctx.input_labels.get("in"))]
        issues: list[Issue] = []
        if c.type not in NUMERIC_TYPES:
            issues.append(
                error(IssueCode.TYPE_MISMATCH, f'"{cfg.column}" é {label(c.type)}, não um número.', column=cfg.column)
            )
        if cfg.mode == "manual":
            if not cfg.boundaries:
                issues.append(error(IssueCode.INVALID_CONFIG, "Informe pelo menos um limite de faixa."))
            elif sorted(cfg.boundaries) != cfg.boundaries or len(set(cfg.boundaries)) != len(cfg.boundaries):
                issues.append(
                    error(IssueCode.INVALID_CONFIG, "Os limites precisam estar em ordem crescente, sem repetir.")
                )
        if out_name(cfg) != cfg.column and schema.has(out_name(cfg)):
            issues.append(error(IssueCode.DUPLICATE_COLUMN, f'Já existe uma coluna "{out_name(cfg)}".'))
        return issues

    def infer_schema(self, cfg: BinConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        return Schema(columns=[*inputs["in"].columns, Column(name=out_name(cfg), type=L.TEXT)])

    def compile(
        self, cfg: BinConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        ref = col(cfg.column)
        e: exp.Expr
        if cfg.mode == "manual":
            labels = manual_labels(cfg)
            case = exp.Case()
            for b, text in zip(cfg.boundaries, labels, strict=False):
                case = case.when(exp.LT(this=ref.copy(), expression=lit(b)), lit(text))
            e = case.else_(lit(labels[-1])) if labels else exp.Null()
            e = exp.Case().when(exp.Is(this=ref.copy(), expression=exp.Null()), exp.Null()).else_(e)
        else:
            # Equal-width ranges between the column min and max, numbered "1 de N" … with their limits.
            n = cfg.count
            idx = tmpl(
                "LEAST(CAST(FLOOR((CAST(_0 AS DOUBLE) - MIN(_0) OVER ()) / NULLIF((MAX(_0) OVER () - MIN(_0) OVER ()) "
                "/ _1, 0)) AS BIGINT), _1 - 1)",
                ref,
                lit(n),
            )
            lo = tmpl("MIN(_0) OVER () + _1 * (MAX(_0) OVER () - MIN(_0) OVER ()) / _2", ref, idx, lit(n))
            hi = tmpl("MIN(_0) OVER () + (_1 + 1) * (MAX(_0) OVER () - MIN(_0) OVER ()) / _2", ref, idx.copy(), lit(n))
            range_text = tmpl(
                "REPLACE(FORMAT('{:.2f}', _0), '.', ',') || ' a ' || REPLACE(FORMAT('{:.2f}', _1), '.', ',')", lo, hi
            )
            e = (
                exp.Case()
                .when(exp.Is(this=ref.copy(), expression=exp.Null()), exp.Null())
                .else_(
                    exp.Coalesce(
                        this=range_text, expressions=[exp.Cast(this=ref.copy(), to=exp.DataType.build("VARCHAR"))]
                    )
                )
            )
        exprs: list[exp.Expr] = [col(c.name) for c in schemas["in"]]
        exprs.append(alias(e, out_name(cfg)))
        return project(inputs["in"], exprs)
