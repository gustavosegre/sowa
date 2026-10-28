from __future__ import annotations

from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error, warning
from forja.domain.schema import Column, Schema
from forja.domain.types import LogicalType, unify
from forja.formula.functions import to_text
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, from_input, lit
from forja.nodes.registry import register_node

L = LogicalType


class UnpivotConfig(NodeConfig):
    columns: list[str] = []  # columns that become rows
    name_column: str = "atributo"
    value_column: str = "valor"
    drop_nulls: bool = False


def value_type(cfg: UnpivotConfig, schema: Schema) -> tuple[LogicalType, bool]:
    """(type, compatible). Incompatible types fall back to Text."""
    result: LogicalType | None = None
    for name in cfg.columns:
        if not schema.has(name):
            continue
        t = schema.type_of(name)
        if result is None:
            result = t
            continue
        u = unify(result, t)
        if u is None:
            return L.TEXT, False
        result = u
    return result or L.TEXT, True


@register_node
class UnpivotNode(NodeSpec[UnpivotConfig]):
    type = "unpivot"
    config_model = UnpivotConfig
    label = "Despivotar"
    category = "aggregate"
    description = "Transforma colunas em linhas (atributo, valor)."

    def validate(self, cfg: UnpivotConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        issues: list[Issue] = [
            column_not_found(c, where=ctx.input_labels.get("in")) for c in cfg.columns if not schema.has(c)
        ]
        if not cfg.columns:
            issues.append(error(IssueCode.INVALID_CONFIG, "Escolha as colunas que viram linhas."))
        kept = {c.name for c in schema if c.name not in cfg.columns}
        for n in (cfg.name_column, cfg.value_column):
            if not n.strip():
                issues.append(
                    error(IssueCode.EMPTY_NAME, "Os nomes das colunas de atributo e valor não podem ficar vazios.")
                )
            elif n in kept:
                issues.append(error(IssueCode.DUPLICATE_COLUMN, f'Já existe uma coluna "{n}".', column=n))
        if cfg.name_column == cfg.value_column:
            issues.append(
                error(IssueCode.DUPLICATE_COLUMN, "As colunas de atributo e valor precisam ter nomes diferentes.")
            )
        if not issues and not value_type(cfg, schema)[1]:
            issues.append(
                warning(
                    IssueCode.TYPE_MISMATCH,
                    "As colunas escolhidas têm tipos diferentes; os valores foram convertidos para Texto.",
                    hint='Converta antes com "Alterar tipo" se quiser manter números ou datas.',
                )
            )
        return issues

    def infer_schema(self, cfg: UnpivotConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        schema = inputs["in"]
        keep = [c for c in schema if c.name not in cfg.columns]
        t, _ = value_type(cfg, schema)
        return Schema(columns=[*keep, Column(name=cfg.name_column, type=L.TEXT), Column(name=cfg.value_column, type=t)])

    def compile(
        self, cfg: UnpivotConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        # Explicit UNION ALL of one SELECT per column: predictable order and types.
        schema = schemas["in"]
        keep = [col(c.name) for c in schema if c.name not in cfg.columns]
        t, compatible = value_type(cfg, schema)
        selects: list[exp.Select] = []
        for name in cfg.columns:
            v: exp.Expr = col(name)
            if not compatible:
                v = to_text(v, schema.type_of(name), ctx.locale)
            elif schema.type_of(name) != t:
                v = exp.Cast(this=v, to=exp.DataType.build("DOUBLE" if t is L.DECIMAL else "TIMESTAMP"))
            q = exp.select(*[k.copy() for k in keep], alias(lit(name), cfg.name_column), alias(v, cfg.value_column))
            q = q.from_(from_input(inputs["in"]))
            if cfg.drop_nulls:
                q = q.where(exp.Not(this=exp.Is(this=col(name), expression=exp.Null())))
            selects.append(q)
        union: exp.Expr = selects[0]
        for s in selects[1:]:
            union = exp.Union(this=union, expression=s, distinct=False)
        sub = exp.Subquery(this=union, alias=exp.TableAlias(this=exp.to_identifier("__unpivot")))
        return exp.select(exp.Star()).from_(sub)
