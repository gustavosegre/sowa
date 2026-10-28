from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error, plural, warning
from forja.domain.schema import Column, Schema
from forja.domain.types import LogicalType, label
from forja.nodes._convert import DecimalSeparator, convert, is_failure, supported
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, QueryRunner, alias, col, count_star, lit, project
from forja.nodes.registry import register_node


class CastRule(BaseModel):
    column: str
    to: LogicalType
    # Date/time format: strftime ("%d/%m/%Y") or Excel style ("dd/mm/aaaa").
    format: str | None = None
    decimal_separator: DecimalSeparator | None = None
    precision: int | None = Field(default=None, ge=1, le=38)
    scale: int | None = Field(default=None, ge=0, le=37)
    on_error: Literal["null", "error"] = "null"


class CastConfig(NodeConfig):
    casts: list[CastRule] = []


@register_node
class CastNode(NodeSpec[CastConfig]):
    type = "cast"
    config_model = CastConfig
    label = "Alterar tipo"
    category = "columns"
    description = "Converte o tipo das colunas (datas, decimais BR, booleanos) com relatório de falhas."

    def validate(self, cfg: CastConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        issues: list[Issue] = []
        seen: set[str] = set()
        for r in cfg.casts:
            c = schema.get(r.column)
            if c is None:
                issues.append(column_not_found(r.column, where=ctx.input_labels.get("in")))
                continue
            if r.column in seen:
                issues.append(
                    error(
                        IssueCode.DUPLICATE_COLUMN,
                        f'A coluna "{r.column}" aparece em duas regras.',
                        column=r.column,
                        hint="Mantenha só uma regra por coluna.",
                    )
                )
            seen.add(r.column)
            if not supported(c.type, r.to):
                issues.append(
                    error(
                        IssueCode.TYPE_MISMATCH,
                        f'Não é possível converter "{r.column}" de {label(c.type)} para {label(r.to)}.',
                        column=r.column,
                        hint="Converta antes para Texto, ou escolha outro tipo.",
                    )
                )
            if r.scale is not None and r.precision is not None and r.scale > r.precision:
                issues.append(
                    error(
                        IssueCode.INVALID_CONFIG,
                        f'Em "{r.column}", as casas decimais não podem passar da precisão.',
                        column=r.column,
                    )
                )
        return issues

    def infer_schema(self, cfg: CastConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        rules = {r.column: r for r in cfg.casts}
        return Schema(
            columns=[Column(name=c.name, type=rules[c.name].to if c.name in rules else c.type) for c in inputs["in"]]
        )

    def _converted(self, r: CastRule, src: LogicalType, ctx: NodeContext) -> exp.Expr:
        return convert(
            col(r.column),
            src,
            r.to,
            fmt=r.format,
            decimal_separator=r.decimal_separator,
            precision=r.precision,
            scale=r.scale,
            locale=ctx.locale,
        )

    def compile(
        self, cfg: CastConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        rules = {r.column: r for r in cfg.casts}
        exprs: list[exp.Expr] = []
        for c in schemas["in"]:
            r = rules.get(c.name)
            if r is None:
                exprs.append(col(c.name))
                continue
            conv = self._converted(r, c.type, ctx)
            if r.on_error == "error":
                msg = f'Valor não convertido na coluna "{r.column}" para {label(r.to)}.'
                conv = exp.Case().when(is_failure(col(c.name), c.type, conv), exp.func("ERROR", lit(msg))).else_(conv)
            exprs.append(alias(conv, c.name))
        return project(inputs["in"], exprs)

    def runtime_issues(
        self,
        cfg: CastConfig,
        inputs: dict[str, exp.Select],
        output: exp.Select,
        schemas: dict[str, Schema],
        ctx: NodeContext,
        run: QueryRunner,
    ) -> list[Issue]:
        schema = schemas["in"]
        checks: list[tuple[CastRule, exp.Expr, LogicalType]] = []
        for r in cfg.casts:
            c = schema.get(r.column)
            if c is None or c.type == r.to:
                continue
            checks.append((r, is_failure(col(r.column), c.type, self._converted(r, c.type, ctx)), c.type))
        if not checks:
            return []
        counts_q = project(
            inputs["in"],
            [
                alias(exp.Filter(this=count_star(), expression=exp.Where(this=cond)), f"c{i}")
                for i, (_, cond, _) in enumerate(checks)
            ],
        )
        counts = run(counts_q)[0]
        issues: list[Issue] = []
        for (r, cond, src_t), n in zip(checks, counts, strict=True):
            if not n:
                continue
            examples_q = (
                exp.select(exp.Cast(this=col(r.column), to=exp.DataType.build("VARCHAR")))
                .distinct()
                .from_(inputs["in"].args["from_"].this.copy())
                .where(cond.copy())
                .limit(5)
            )
            examples = [str(row[0]) for row in run(examples_q)]
            fmt_hint = f' no formato "{r.format}"' if r.format else ""
            issues.append(
                warning(
                    IssueCode.CAST_FAILURES,
                    f"{plural(int(n), 'valor não convertido', 'valores não convertidos')} "
                    f'em "{r.column}" para {label(r.to)}{fmt_hint}. '
                    + ("Eles ficaram vazios." if r.on_error == "null" else "A exportação vai falhar."),
                    column=r.column,
                    count=int(n),
                    examples=examples,
                    hint="Confira o formato ou o separador decimal da regra." if src_t is LogicalType.TEXT else None,
                )
            )
        return issues
