from __future__ import annotations

from typing import Literal

from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, error, warning
from sowa.domain.schema import Column, Schema
from sowa.domain.types import LogicalType, to_duckdb, unify
from sowa.formula.functions import to_text
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, from_input, lit
from sowa.nodes.registry import register_node

L = LogicalType


class UnionConfig(NodeConfig):
    # by_name: columns aligned by name (missing ones become empty) · by_position: by order
    mode: Literal["by_name", "by_position"] = "by_name"
    # Optional column telling which input each row came from.
    source_column: str | None = None


def _handles(inputs: dict[str, Schema]) -> list[str]:
    return sorted(inputs, key=lambda h: int(h.split("_")[1]) if "_" in h else 0)


def plan(cfg: UnionConfig, inputs: dict[str, Schema]) -> tuple[list[Column], bool]:
    """(output columns, every type was compatible)."""
    handles = _handles(inputs)
    ok = True
    if cfg.mode == "by_name":
        names: list[str] = []
        for h in handles:
            names += [c.name for c in inputs[h] if c.name not in names]
        cols: list[Column] = []
        for n in names:
            t: LogicalType | None = None
            for h in handles:
                c = inputs[h].get(n)
                if c is None:
                    continue
                u = c.type if t is None else unify(t, c.type)
                if u is None:
                    ok, u = False, L.TEXT
                t = u
            cols.append(Column(name=n, type=t or L.TEXT))
        return cols, ok
    width = max(len(inputs[h]) for h in handles)
    first = inputs[handles[0]]
    cols = []
    for i in range(width):
        t = None
        for h in handles:
            if i < len(inputs[h]):
                ct = inputs[h].columns[i].type
                u = ct if t is None else unify(t, ct)
                if u is None:
                    ok, u = False, L.TEXT
                t = u
        name = first.columns[i].name if i < len(first) else f"coluna_{i + 1}"
        cols.append(Column(name=name, type=t or L.TEXT))
    return cols, ok


@register_node
class UnionNode(NodeSpec[UnionConfig]):
    type = "union"
    config_model = UnionConfig
    label = "Empilhar"
    category = "combine"
    description = "Empilha tabelas, alinhando por nome ou posição; colunas faltantes ficam vazias."
    inputs = ("in_0", "in_1")
    variadic_inputs = True

    def validate(self, cfg: UnionConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        issues: list[Issue] = []
        if len(inputs) < 2:
            issues.append(error(IssueCode.MISSING_INPUT, "Conecte pelo menos duas tabelas para empilhar."))
            return issues
        cols, ok = plan(cfg, inputs)
        if cfg.source_column and any(c.name == cfg.source_column for c in cols):
            issues.append(error(IssueCode.DUPLICATE_COLUMN, f'Já existe uma coluna "{cfg.source_column}".'))
        if not ok:
            issues.append(
                warning(
                    IssueCode.TYPE_MISMATCH,
                    "Há colunas com tipos diferentes entre as tabelas; elas foram convertidas para Texto.",
                    hint='Use "Alterar tipo" antes de empilhar para manter números e datas.',
                )
            )
        return issues

    def infer_schema(self, cfg: UnionConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        cols, _ = plan(cfg, inputs)
        if cfg.source_column:
            cols = [*cols, Column(name=cfg.source_column, type=L.TEXT)]
        return Schema(columns=cols)

    def compile(
        self, cfg: UnionConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        out, _ = plan(cfg, schemas)
        selects: list[exp.Select] = []
        for h in _handles(schemas):
            s = schemas[h]
            exprs: list[exp.Expr] = []
            for i, c in enumerate(out):
                src = s.get(c.name) if cfg.mode == "by_name" else (s.columns[i] if i < len(s) else None)
                if src is None:
                    e: exp.Expr = exp.Cast(this=exp.Null(), to=to_duckdb(c.type))
                elif src.type == c.type:
                    e = col(src.name)
                elif c.type is L.TEXT:
                    e = to_text(col(src.name), src.type, ctx.locale)
                else:
                    e = exp.Cast(this=col(src.name), to=to_duckdb(c.type))
                exprs.append(alias(e, c.name))
            if cfg.source_column:
                exprs.append(alias(lit(ctx.input_labels.get(h, h)), cfg.source_column))
            selects.append(exp.select(*exprs).from_(from_input(inputs[h])))
        union: exp.Expr = selects[0]
        for s2 in selects[1:]:
            union = exp.Union(this=union, expression=s2, distinct=False)
        return exp.select(exp.Star()).from_(
            exp.Subquery(this=union, alias=exp.TableAlias(this=exp.to_identifier("__u")))
        )
