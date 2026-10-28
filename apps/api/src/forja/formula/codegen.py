"""Typed AST -> SQLGlot expression (DuckDB)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlglot import exp

from forja.domain.pipeline import Parameter
from forja.domain.types import NUMERIC_TYPES, TEMPORAL_TYPES, LogicalType
from forja.formula import ast
from forja.formula.functions import as_double, as_int, lit_str, tmpl, to_text
from forja.formula.typecheck import Typed

L = LogicalType


@dataclass
class GenCtx:
    locale: str = "pt-BR"
    params: dict[str, Parameter] = field(default_factory=dict)
    # Divisor expressions, so the node can report how many rows divided by zero.
    div_guards: list[exp.Expr] = field(default_factory=list)


def col(name: str) -> exp.Column:
    return exp.Column(this=exp.to_identifier(name, quoted=True))


def _p(e: exp.Expr) -> exp.Expr:
    return exp.Paren(this=e) if isinstance(e, (exp.Binary, exp.Unary, exp.Not)) else e


_COMPARISONS: dict[str, type[exp.Binary]] = {
    "=": exp.EQ,
    "<>": exp.NEQ,
    "<": exp.LT,
    ">": exp.GT,
    "<=": exp.LTE,
    ">=": exp.GTE,
}


def generate(t: Typed, ctx: GenCtx) -> exp.Expr:
    node = t.node
    match node:
        case ast.NumberLit():
            return exp.Literal.number(node.value)
        case ast.StringLit():
            return lit_str(node.value)
        case ast.BoolLit():
            return exp.Boolean(this=node.value)
        case ast.ColumnRef():
            return col(node.name)
        case ast.ParamRef():
            from forja.nodes._values import typed_literal

            p = ctx.params[node.name]
            return typed_literal(p.value, p.type, ctx.locale)
        case ast.Unary():
            inner = generate(t.children[0], ctx)
            return inner if node.op == "+" else exp.Neg(this=_p(inner))
        case ast.Percent():
            return exp.Div(this=as_double(generate(t.children[0], ctx)), expression=exp.Literal.number(100))
        case ast.Binary():
            return _binary(t, node, ctx)
        case ast.Call():
            assert t.func is not None
            args = [generate(c, ctx) for c in t.children]
            return t.func.codegen(args, t.children, ctx)
    raise AssertionError(f"unknown node {node!r}")  # pragma: no cover


def _binary(t: Typed, node: ast.Binary, ctx: GenCtx) -> exp.Expr:
    lt, rt = t.children[0].type, t.children[1].type
    left = _p(generate(t.children[0], ctx))
    right = _p(generate(t.children[1], ctx))
    op = node.op
    if op == "&":
        lhs = exp.Coalesce(this=to_text(left, lt, ctx.locale), expressions=[lit_str("")])
        rhs = exp.Coalesce(this=to_text(right, rt, ctx.locale), expressions=[lit_str("")])
        return exp.DPipe(this=lhs, expression=rhs)
    if op in ("+", "-"):
        if lt in TEMPORAL_TYPES and rt in NUMERIC_TYPES:
            return _date_shift(left, lt, right, rt, op)
        if lt in NUMERIC_TYPES and rt in TEMPORAL_TYPES:
            return _date_shift(right, rt, left, lt, op)
        return exp.Add(this=left, expression=right) if op == "+" else exp.Sub(this=left, expression=right)
    if op == "*":
        return exp.Mul(this=left, expression=right)
    if op == "/":
        ctx.div_guards.append(right)
        return (
            exp.Case()
            .when(exp.EQ(this=right, expression=exp.Literal.number(0)), exp.Null())
            .else_(exp.Div(this=as_double(left), expression=right))
        )
    if op == "^":
        return exp.Pow(this=as_double(left), expression=right)
    cls = _COMPARISONS[op]
    if lt is L.TEXT and rt is L.TEXT:
        # Excel compares text without case sensitivity.
        return cls(this=exp.Lower(this=left), expression=exp.Lower(this=right))
    return cls(this=left, expression=right)


def _date_shift(d: exp.Expr, dt: LogicalType, n: exp.Expr, nt: LogicalType, op: str) -> exp.Expr:
    days = as_int(n, nt)
    if dt is L.DATE:
        return exp.Add(this=d, expression=days) if op == "+" else exp.Sub(this=d, expression=days)
    sign = "+" if op == "+" else "-"
    return tmpl(f"_0 {sign} TO_DAYS(CAST(_1 AS INTEGER))", d, days)
