"""Pivot table (CLAUDE.md §10). Compiled as conditional aggregation over an explicit value list."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error, plural, warning
from sowa.domain.schema import Column, Schema
from sowa.domain.types import TEMPORAL_TYPES, LogicalType, to_duckdb
from sowa.formula.functions import tmpl
from sowa.nodes._aggs import AGG_LABELS, AggFn, Aggregation, agg_expr, agg_type, validate_agg
from sowa.nodes._conditions import Condition, ConditionBuilder, ConditionGroup
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, QueryRunner, alias, col, from_input, lit
from sowa.nodes.registry import register_node

L = LogicalType
MAX_COLUMN_VALUES = 200
NULL_LABEL = "(vazio)"
TOTAL_LABEL = "(Total)"

DateGroup = Literal["none", "year", "quarter", "month", "day"]
_GROUP_SUFFIX = {"year": "ano", "quarter": "trimestre", "month": "mês", "day": "dia"}


class PivotField(BaseModel):
    column: str
    date_group: DateGroup = "none"


ShowAs = Literal["normal", "pct_total", "pct_row", "pct_column", "difference", "running_total"]
# "Diferença de" and "Soma acumulada em" of Excel: computed along a base field.
RELATIVE: frozenset[str] = frozenset({"difference", "running_total"})


class PivotValue(BaseModel):
    column: str | None = None
    fn: AggFn = "sum"
    show_as: ShowAs = "normal"
    # difference / running_total: a field in "Linhas" or the "Colunas" field (its name in the table,
    # e.g. "data (mês)"); difference compares with the previous item or with a fixed one.
    base_field: str | None = None
    base_item: Literal["previous", "fixed"] = "previous"
    base_value: str | None = None
    label: str | None = None


class PivotConfig(NodeConfig):
    rows: list[PivotField] = []
    columns: PivotField | None = None
    values: list[PivotValue] = []
    filters: list[Condition] = []
    # Distinct values of the "Colunas" field, resolved when configuring (explicit list, never dynamic).
    column_values: list[str | None] = []
    name_template: str = "{valor} · {medida}"
    totals: bool = False


def field_name(f: PivotField) -> str:
    return f.column if f.date_group == "none" else f"{f.column} ({_GROUP_SUFFIX[f.date_group]})"


def field_expr(f: PivotField, schema: Schema) -> exp.Expr:
    c = col(f.column)
    if f.date_group == "none" or not schema.has(f.column) or schema.type_of(f.column) not in TEMPORAL_TYPES:
        return c
    sql = {
        "year": "CAST(YEAR(_0) AS BIGINT)",
        "quarter": "CAST(YEAR(_0) AS VARCHAR) || '-T' || CAST(QUARTER(_0) AS VARCHAR)",
        "month": "STRFTIME(CAST(_0 AS DATE), '%Y-%m')",
        "day": "CAST(_0 AS DATE)",
    }[f.date_group]
    return tmpl(sql, c)


def field_type(f: PivotField, schema: Schema) -> LogicalType:
    t = schema.type_of(f.column)
    if f.date_group == "none" or t not in TEMPORAL_TYPES:
        return t
    return {"year": L.INTEGER, "quarter": L.TEXT, "month": L.TEXT, "day": L.DATE}[f.date_group]


def as_text(e: exp.Expr) -> exp.Expr:
    return exp.Cast(this=e, to=exp.DataType.build("VARCHAR"))


def measure_label(v: PivotValue) -> str:
    if v.label and v.label.strip():
        return v.label
    if v.fn == "count":
        return "Contagem"
    return f"{AGG_LABELS[v.fn]} de {v.column}"


def value_type(v: PivotValue, schema: Schema) -> LogicalType:
    t = agg_type(Aggregation(column=v.column, fn=v.fn), schema)
    if v.show_as in RELATIVE:
        return L.INTEGER if t is L.INTEGER else L.DECIMAL
    if v.show_as != "normal":
        return L.DECIMAL
    return t


def _relative_issues(cfg: PivotConfig, v: PivotValue, schema: Schema) -> list[Issue]:
    what = "Diferença de" if v.show_as == "difference" else "Soma acumulada em"
    label = measure_label(v)
    rows = [field_name(f) for f in cfg.rows]
    cols = field_name(cfg.columns) if cfg.columns else None
    if agg_type(Aggregation(column=v.column, fn=v.fn), schema) not in (L.INTEGER, L.DECIMAL):
        return [error(IssueCode.INVALID_CONFIG, f'"{what}" precisa de uma medida numérica ("{label}" não é).')]
    if not v.base_field:
        return [
            error(
                IssueCode.INVALID_CONFIG,
                f'Escolha o campo base de "{what}" em "{label}".',
                hint="Um campo de Linhas ou o campo de Colunas.",
            )
        ]
    if v.base_field not in rows and v.base_field != cols:
        return [
            error(
                IssueCode.INVALID_CONFIG,
                f'O campo base "{v.base_field}" de "{label}" não está em Linhas nem em Colunas.',
                hint="Escolha outro campo base.",
            )
        ]
    out: list[Issue] = []
    if v.base_field in rows and cfg.totals:
        out.append(
            error(
                IssueCode.INVALID_CONFIG,
                f'"{what}" com campo base em Linhas não funciona com totais ("{label}").',
                hint="Desligue os totais ou use o campo de Colunas como base.",
            )
        )
    if v.show_as == "difference" and v.base_item == "fixed":
        if not v.base_value:
            out.append(error(IssueCode.INVALID_CONFIG, f'Escolha o item fixo de "{what}" em "{label}".'))
        elif v.base_field == cols and v.base_value not in cfg.column_values:
            out.append(
                error(
                    IssueCode.INVALID_CONFIG,
                    f'O item "{v.base_value}" não está entre os valores de "{cols}".',
                    hint='Escolha outro item ou clique em "Atualizar colunas".',
                )
            )
    return out


def value_label(cv: str | None, cfg: PivotConfig, schema: Schema) -> str:
    """How a value of the "Colunas" field is shown in generated column names."""
    if cv is None:
        return NULL_LABEL
    f = cfg.columns
    if f is not None and schema.has(f.column) and schema.type_of(f.column) is L.BOOLEAN:
        return {"true": "verdadeiro", "false": "falso"}.get(cv, cv)
    return cv


def output_columns(cfg: PivotConfig, schema: Schema) -> list[tuple[str, LogicalType]]:
    out = [(field_name(f), L.TEXT if cfg.totals else field_type(f, schema)) for f in cfg.rows]
    if cfg.columns is None:
        out += [(measure_label(v), value_type(v, schema)) for v in cfg.values]
        return out
    for cv in cfg.column_values:
        for v in cfg.values:
            shown = value_label(cv, cfg, schema)
            name = (
                cfg.name_template.replace("{valor}", shown).replace("{medida}", measure_label(v))
                if len(cfg.values) > 1
                else shown
            )
            out.append((name, value_type(v, schema)))
    return out


@register_node
class PivotNode(NodeSpec[PivotConfig]):
    type = "pivot"
    config_model = PivotConfig
    label = "Tabela dinâmica"
    category = "aggregate"
    description = "Filtros, Linhas, Colunas e Valores, como a dinâmica do Excel."
    cacheable = True

    def validate(self, cfg: PivotConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        where = ctx.input_labels.get("in")
        issues: list[Issue] = []
        fields = [*cfg.rows, *([cfg.columns] if cfg.columns else [])]
        issues += [column_not_found(f.column, where=where) for f in fields if not schema.has(f.column)]
        if not cfg.values:
            issues.append(
                error(
                    IssueCode.INVALID_CONFIG,
                    'Arraste pelo menos um campo para "Valores".',
                    hint="Ex.: Soma de receita.",
                )
            )
        for v in cfg.values:
            issues += validate_agg(Aggregation(column=v.column, fn=v.fn), schema, where)
            if v.show_as in RELATIVE:
                issues += _relative_issues(cfg, v, schema)
        b = ConditionBuilder(schema, ctx)
        b.group(ConditionGroup(conditions=list(cfg.filters)))
        issues += b.issues
        if cfg.columns is not None:
            if len(cfg.column_values) > MAX_COLUMN_VALUES:
                issues.append(
                    error(
                        IssueCode.PIVOT_TOO_MANY_VALUES,
                        f'"{cfg.columns.column}" tem {len(cfg.column_values)} valores distintos; o limite em Colunas é '
                        f"{MAX_COLUMN_VALUES}.",
                        hint='Use o campo em "Linhas" ou agrupe os valores antes (ex.: Faixas ou Agrupar).',
                    )
                )
            elif not cfg.column_values:
                issues.append(
                    error(
                        IssueCode.PIVOT_NEW_VALUES,
                        f'Carregue os valores de "{cfg.columns.column}" para montar as colunas.',
                        hint='Clique em "Atualizar colunas".',
                    )
                )
        names = [n for n, _ in output_columns(cfg, schema)]
        dup = {n for n in names if names.count(n) > 1}
        if dup:
            issues.append(
                error(
                    IssueCode.DUPLICATE_COLUMN,
                    f"Colunas de saída repetidas: {', '.join(sorted(dup))}.",
                    hint="Dê rótulos diferentes às medidas ou ajuste o modelo de nome.",
                )
            )
        return issues

    def infer_schema(self, cfg: PivotConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        return Schema(columns=[Column(name=n, type=t) for n, t in output_columns(cfg, inputs["in"])])

    def compile(
        self, cfg: PivotConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        schema = schemas["in"]
        row_exprs = [field_expr(f, schema) for f in cfg.rows]
        names = [n for n, _ in output_columns(cfg, schema)]
        out: list[exp.Expr] = []
        for f, e in zip(cfg.rows, row_exprs, strict=True):
            if cfg.totals:
                labelled = exp.Case().when(
                    exp.EQ(this=exp.func("GROUPING", e.copy()), expression=lit(1)), lit(TOTAL_LABEL)
                )
                out.append(alias(labelled.else_(as_text(e.copy())), field_name(f)))
            else:
                out.append(alias(e.copy(), field_name(f)))
        detail = (
            exp.EQ(this=exp.func("GROUPING", *[e.copy() for e in row_exprs]), expression=lit(0))
            if cfg.totals and row_exprs
            else None
        )

        def measure(v: PivotValue, cond: exp.Expr | None) -> exp.Expr:
            agg = Aggregation(column=v.column, fn=v.fn)
            cell = agg_expr(agg, schema, cond)
            if v.show_as == "normal" or v.show_as in RELATIVE:  # relative ones are built on the plain cell
                return cell
            dbl = exp.Cast(this=cell, to=exp.DataType.build("DOUBLE"))
            if v.show_as == "pct_row":
                denom: exp.Expr = agg_expr(agg, schema)
            else:
                # Column/grand totals over detail rows only (totals rows would count twice).
                base = agg_expr(agg, schema, cond if v.show_as == "pct_column" else None)
                if detail is not None:
                    base = exp.Case().when(detail.copy(), base)
                denom = exp.Window(this=exp.Sum(this=base))
            return exp.Div(this=dbl, expression=exp.Nullif(this=denom, expression=lit(0)))

        row_names = [field_name(f) for f in cfg.rows]

        def typed(v: PivotValue, e: exp.Expr) -> exp.Expr:
            return exp.Cast(this=e, to=to_duckdb(value_type(v, schema)))

        def on_rows(v: PivotValue) -> bool:
            return v.show_as in RELATIVE and v.base_field in row_names

        def along_rows(v: PivotValue, cell: exp.Expr) -> exp.Expr:
            """Difference / running total along a "Linhas" field, within the other row fields."""
            idx = row_names.index(v.base_field or "")
            base = row_exprs[idx]
            part = [e.copy() for j, e in enumerate(row_exprs) if j != idx]
            order = exp.Order(expressions=[exp.Ordered(this=base.copy(), nulls_first=False)])
            if v.show_as == "running_total":
                spec = exp.WindowSpec(kind="ROWS", start="UNBOUNDED", start_side="PRECEDING", end="CURRENT ROW")
                return exp.Window(this=exp.Sum(this=cell), partition_by=part, order=order, spec=spec)
            if v.base_item == "previous":
                ref: exp.Expr = exp.Window(this=exp.func("LAG", cell.copy()), partition_by=part, order=order)
            else:
                hit = exp.EQ(this=as_text(base.copy()), expression=lit(v.base_value))
                ref = exp.Window(this=exp.Max(this=exp.Case().when(hit, cell.copy())), partition_by=part)
            return exp.Sub(this=cell, expression=ref)

        def along_columns(v: PivotValue, cells: list[exp.Expr], k: int) -> exp.Expr:
            """Difference / running total across the generated columns (in the order of column_values)."""
            if v.show_as == "running_total":
                total: exp.Expr = exp.Coalesce(this=cells[0].copy(), expressions=[lit(0)])
                for c in cells[1 : k + 1]:
                    total = exp.Add(this=total, expression=exp.Coalesce(this=c.copy(), expressions=[lit(0)]))
                return total
            j = k - 1 if v.base_item == "previous" else cfg.column_values.index(v.base_value)
            return exp.Null() if j < 0 else exp.Sub(this=cells[k].copy(), expression=cells[j].copy())

        i = len(out)
        if cfg.columns is None:
            for v in cfg.values:
                cell = measure(v, None)
                out.append(alias(typed(v, along_rows(v, cell)) if on_rows(v) else cell, names[i]))
                i += 1
        else:
            key = as_text(field_expr(cfg.columns, schema))
            conds: list[exp.Expr] = [
                exp.Is(this=key.copy(), expression=exp.Null())
                if cv is None
                else exp.EQ(this=key.copy(), expression=lit(cv))
                for cv in cfg.column_values
            ]
            across = {
                vi: [agg_expr(Aggregation(column=v.column, fn=v.fn), schema, c) for c in conds]
                for vi, v in enumerate(cfg.values)
                if v.show_as in RELATIVE and not on_rows(v)
            }
            for k, cond in enumerate(conds):
                for vi, v in enumerate(cfg.values):
                    if vi in across:
                        e = typed(v, along_columns(v, across[vi], k))
                    elif on_rows(v):
                        e = typed(v, along_rows(v, measure(v, cond)))
                    else:
                        e = measure(v, cond)
                    out.append(alias(e, names[i]))
                    i += 1
        sel = exp.select(*out).from_(from_input(inputs["in"]))
        if cfg.filters:
            where = ConditionBuilder(schema, ctx).group(ConditionGroup(conditions=list(cfg.filters)))
            if where is not None:
                sel = sel.where(where)
        if row_exprs:
            group = [e.copy() for e in row_exprs]
            sel = sel.group_by(exp.Rollup(expressions=group)) if cfg.totals else sel.group_by(*group)
            # Keep the result ordered like a pivot table (totals last).
            order: list[exp.Expr] = []
            if cfg.totals:
                # Subtotal/total rows after their details (the output alias is text, so sort on GROUPING).
                order.append(exp.Ordered(this=exp.func("GROUPING", *[e.copy() for e in row_exprs])))
            order += [exp.Ordered(this=e.copy(), nulls_first=False) for e in row_exprs]
            sel = sel.order_by(*order)
        return sel

    def runtime_issues(
        self,
        cfg: PivotConfig,
        inputs: dict[str, exp.Select],
        output: exp.Select,
        schemas: dict[str, Schema],
        ctx: NodeContext,
        run: QueryRunner,
    ) -> list[Issue]:
        if cfg.columns is None or not cfg.column_values:
            return []
        key = as_text(field_expr(cfg.columns, schemas["in"]))
        known = [v for v in cfg.column_values if v is not None]
        q = exp.select(key).distinct().from_(from_input(inputs["in"]))
        conds: list[exp.Expr] = [exp.Not(this=exp.Is(this=key.copy(), expression=exp.Null()))]
        if known:
            conds.append(exp.Not(this=exp.In(this=key.copy(), expressions=[lit(v) for v in known])))
        rows = run(q.where(exp.and_(*conds)).limit(MAX_COLUMN_VALUES + 1))
        if not rows:
            return []
        n = len(rows)
        return [
            warning(
                IssueCode.PIVOT_NEW_VALUES,
                f'{plural(n, "valor novo", "valores novos")} em "{cfg.columns.column}" — atualizar colunas?',
                hint='Clique em "Atualizar colunas" no painel do nó.',
                count=n,
                examples=[str(r[0]) for r in rows[:5]],
            )
        ]
