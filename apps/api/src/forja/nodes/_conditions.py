"""Visual conditions (groups E/OU) shared by filter, conditional and pivot filters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error
from forja.domain.schema import Schema
from forja.domain.types import LogicalType, label
from forja.formula.parser import Locale
from forja.nodes._values import Scalar, ValueError_, typed_literal, value_error_message
from forja.nodes.base import NodeContext, col, lit

L = LogicalType

Operator = Literal[
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "between",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "in",
    "not_in",
    "is_null",
    "is_not_null",
    "is_true",
    "is_false",
]

OPERATOR_LABELS: dict[str, str] = {
    "eq": "=",
    "neq": "≠",
    "gt": ">",
    "gte": "≥",
    "lt": "<",
    "lte": "≤",
    "between": "entre",
    "contains": "contém",
    "not_contains": "não contém",
    "starts_with": "começa com",
    "ends_with": "termina com",
    "in": "é um de",
    "not_in": "não é um de",
    "is_null": "está vazio",
    "is_not_null": "não está vazio",
    "is_true": "é verdadeiro",
    "is_false": "é falso",
}

_TEXT_ONLY = {"contains", "not_contains", "starts_with", "ends_with"}
_NO_VALUE = {"is_null", "is_not_null", "is_true", "is_false"}
_ORDERING = {"gt", "gte", "lt", "lte", "between"}


class Condition(BaseModel):
    kind: Literal["condition"] = "condition"
    column: str
    operator: Operator = "eq"
    value: Scalar = None
    value2: Scalar = None
    values: list[Scalar] = []
    case_sensitive: bool = False


class ConditionGroup(BaseModel):
    kind: Literal["group"] = "group"
    op: Literal["and", "or"] = "and"
    conditions: list[Condition | ConditionGroup] = []


def locale_of(ctx: NodeContext) -> Locale:
    return "en-US" if ctx.locale == "en-US" else "pt-BR"


class ConditionBuilder:
    def __init__(self, schema: Schema, ctx: NodeContext) -> None:
        self.schema = schema
        self.ctx = ctx
        self.issues: list[Issue] = []

    def group(self, g: ConditionGroup) -> exp.Expr | None:
        parts = [p for c in g.conditions if (p := self.item(c)) is not None]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return exp.and_(*parts) if g.op == "and" else exp.or_(*parts)

    def item(self, c: Condition | ConditionGroup) -> exp.Expr | None:
        if isinstance(c, ConditionGroup):
            g = self.group(c)
            return exp.Paren(this=g) if g is not None else None
        return self.condition(c)

    def _lit(self, c: Condition, raw: Scalar, t: LogicalType) -> exp.Expr | None:
        # "{data_corte}" as a value refers to a global parameter.
        if isinstance(raw, str) and raw.startswith("{") and raw.endswith("}"):
            p = self.ctx.param(raw[1:-1].strip())
            if p is None:
                self.issues.append(
                    error(IssueCode.PARAM_NOT_FOUND, f"O parâmetro {raw} não existe neste fluxo.", column=c.column)
                )
                return None
            raw = p.value if not isinstance(p.value, bool) else ("sim" if p.value else "não")
        try:
            v = typed_literal(raw, t, self.ctx.locale)
        except ValueError_ as e:
            self.issues.append(
                error(IssueCode.TYPE_MISMATCH, value_error_message(c.column, raw, t, str(e)), column=c.column)
            )
            return None
        if t is L.TEXT and not c.case_sensitive and isinstance(raw, str):
            return lit(raw.lower())
        return v

    def condition(self, c: Condition) -> exp.Expr | None:
        column = self.schema.get(c.column)
        if column is None:
            self.issues.append(column_not_found(c.column, where=self.ctx.input_labels.get("in")))
            return None
        t = column.type
        op = c.operator
        ref: exp.Expr = col(c.column)
        if op in _TEXT_ONLY and t is not L.TEXT:
            self.issues.append(
                error(
                    IssueCode.TYPE_MISMATCH,
                    f'"{OPERATOR_LABELS[op]}" só funciona com Texto, e "{c.column}" é {label(t)}.',
                    column=c.column,
                )
            )
            return None
        if op in ("is_true", "is_false") and t is not L.BOOLEAN:
            self.issues.append(
                error(
                    IssueCode.TYPE_MISMATCH,
                    f'"{OPERATOR_LABELS[op]}" só funciona com colunas verdadeiro/falso.',
                    column=c.column,
                )
            )
            return None
        if op in _ORDERING and t in (L.BOOLEAN, L.OTHER):
            self.issues.append(
                error(IssueCode.TYPE_MISMATCH, f'"{OPERATOR_LABELS[op]}" não funciona com {label(t)}.', column=c.column)
            )
            return None
        if op == "is_null":
            return (
                exp.Is(this=ref, expression=exp.Null())
                if t is not L.TEXT
                else exp.Paren(
                    this=exp.or_(
                        exp.Is(this=ref, expression=exp.Null()), exp.EQ(this=exp.func("TRIM", ref), expression=lit(""))
                    )
                )
            )
        if op == "is_not_null":
            base = exp.Not(this=exp.Is(this=ref, expression=exp.Null()))
            return (
                base
                if t is not L.TEXT
                else exp.and_(base, exp.NEQ(this=exp.func("TRIM", ref.copy()), expression=lit("")))
            )
        if op == "is_true":
            return exp.Is(this=ref, expression=exp.Boolean(this=True))
        if op == "is_false":
            return exp.Is(this=ref, expression=exp.Boolean(this=False))
        if t is L.TEXT and not c.case_sensitive:
            ref = exp.Lower(this=ref)
        if op in ("in", "not_in"):
            vals = [v for raw in c.values if (v := self._lit(c, raw, t)) is not None]
            if not c.values:
                self.issues.append(
                    error(IssueCode.INVALID_CONFIG, f'Informe pelo menos um valor para "{c.column}".', column=c.column)
                )
                return None
            cond: exp.Expr = exp.In(this=ref, expressions=vals)
            if op == "not_in":
                return exp.Paren(this=exp.or_(exp.Is(this=col(c.column), expression=exp.Null()), exp.Not(this=cond)))
            return cond
        if c.value is None or (isinstance(c.value, str) and c.value == "" and t is not L.TEXT):
            self.issues.append(
                error(IssueCode.INVALID_CONFIG, f'Informe o valor para filtrar "{c.column}".', column=c.column)
            )
            return None
        v = self._lit(c, c.value, t)
        if v is None:
            return None
        match op:
            case "eq":
                return exp.EQ(this=ref, expression=v)
            case "neq":
                # Like Excel's filter, "different from" keeps blank cells.
                return exp.Paren(
                    this=exp.or_(exp.Is(this=col(c.column), expression=exp.Null()), exp.NEQ(this=ref, expression=v))
                )
            case "gt":
                return exp.GT(this=ref, expression=v)
            case "gte":
                return exp.GTE(this=ref, expression=v)
            case "lt":
                return exp.LT(this=ref, expression=v)
            case "lte":
                return exp.LTE(this=ref, expression=v)
            case "between":
                v2 = self._lit(c, c.value2, t) if c.value2 is not None else None
                if v2 is None:
                    if c.value2 is None:
                        self.issues.append(
                            error(
                                IssueCode.INVALID_CONFIG,
                                f'Informe o valor final do intervalo de "{c.column}".',
                                column=c.column,
                            )
                        )
                    return None
                return exp.Between(this=ref, low=v, high=v2)
            case "contains":
                return exp.func("CONTAINS", ref, v)
            case "not_contains":
                return exp.Paren(
                    this=exp.or_(
                        exp.Is(this=col(c.column), expression=exp.Null()), exp.Not(this=exp.func("CONTAINS", ref, v))
                    )
                )
            case "starts_with":
                return exp.func("STARTS_WITH", ref, v)
            case "ends_with":
                return exp.func("ENDS_WITH", ref, v)
        return None  # pragma: no cover
