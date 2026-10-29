"""Facade: formula text -> checked type + SQLGlot expression."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, Position
from sowa.domain.pipeline import Parameter
from sowa.domain.schema import Schema
from sowa.domain.types import LogicalType
from sowa.formula import ast
from sowa.formula.codegen import GenCtx, generate
from sowa.formula.parser import FormulaSyntaxError, Locale, parse
from sowa.formula.typecheck import Checker, FormulaContext, FormulaError, referenced_columns


@dataclass
class CompiledFormula:
    ast: ast.Expr
    type: LogicalType
    sql: exp.Expr
    columns: list[str]
    div_guards: list[exp.Expr] = field(default_factory=list)
    is_aggregate: bool = False


def compile_formula(
    text: str,
    schema: Schema,
    *,
    locale: Locale = "pt-BR",
    context: FormulaContext = "row",
    group_keys: Collection[str] = (),
    params: Sequence[Parameter] = (),
) -> CompiledFormula:
    """Parse, type-check and generate SQL. Raises FormulaError on any problem."""
    try:
        tree = parse(text, locale)
    except FormulaSyntaxError as e:
        raise FormulaError(IssueCode.FORMULA_SYNTAX, e.message, e.start, e.end) from None
    by_name = {p.name: p for p in params}
    typed = Checker(schema, context, group_keys, by_name).check(tree)
    ctx = GenCtx(locale=locale, params=by_name)
    sql = generate(typed, ctx)
    return CompiledFormula(tree, typed.type, sql, referenced_columns(tree), ctx.div_guards, typed.is_aggregate)


def formula_issue(err: FormulaError, *, field_label: str = "fórmula") -> Issue:
    return Issue(
        code=err.code,
        message=f"Erro na {field_label}: {err.message}",
        column=err.column,
        position=Position(start=err.start, end=err.end),
        hint="Corrija a fórmula no painel de configuração do nó.",
    )
