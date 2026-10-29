"""Type conversion expressions shared by `cast` and the import wizard."""

from __future__ import annotations

from typing import Literal

from sqlglot import exp

from sowa.domain.types import NUMERIC_TYPES, LogicalType, to_duckdb
from sowa.formula.functions import excel_date_format, tmpl, to_text
from sowa.nodes.base import lit

L = LogicalType

TRUE_WORDS = ("sim", "s", "verdadeiro", "v", "true", "t", "1", "yes", "y")
FALSE_WORDS = ("não", "nao", "n", "falso", "f", "false", "0", "no")

DecimalSeparator = Literal[",", "."]


def strptime_format(fmt: str) -> str:
    """Accept both strftime (`%d/%m/%Y`) and Excel-style (`dd/mm/aaaa`) formats."""
    return fmt if "%" in fmt else excel_date_format(fmt)


def clean_text(e: exp.Expr) -> exp.Expr:
    """Blank text becomes NULL, so it doesn't count as a conversion failure."""
    return tmpl("NULLIF(TRIM(_0), '')", e)


def convert(
    e: exp.Expr,
    src: LogicalType,
    to: LogicalType,
    *,
    fmt: str | None = None,
    decimal_separator: DecimalSeparator | None = None,
    precision: int | None = None,
    scale: int | None = None,
    locale: str = "pt-BR",
) -> exp.Expr:
    """A NULL-on-failure conversion of `e` from `src` to `to`."""
    target = to_duckdb(to, precision, scale)
    if src == to and not (to is L.DECIMAL and precision is not None):
        return e
    if src is L.TEXT:
        v = clean_text(e)
        if to in NUMERIC_TYPES:
            if decimal_separator == ",":
                v = tmpl("REPLACE(REPLACE(REGEXP_REPLACE(_0, '^R\\$\\s*|\\s', '', 'g'), '.', ''), ',', '.')", v)
            elif decimal_separator == ".":
                v = tmpl("REPLACE(REGEXP_REPLACE(_0, '^\\$\\s*|\\s', '', 'g'), ',', '')", v)
            if to is L.INTEGER:
                # "10,0" is a valid integer; "10,5" is not.
                as_dec = exp.TryCast(this=v, to=exp.DataType.build("DOUBLE"))
                return tmpl("CASE WHEN _0 = TRUNC(_0) THEN CAST(_0 AS BIGINT) END", as_dec)
            return exp.TryCast(this=v, to=target)
        if to in (L.DATE, L.DATETIME, L.TIME):
            if fmt:
                parsed = exp.func("TRY_STRPTIME", v, lit(strptime_format(fmt)))
                return exp.Cast(this=parsed, to=target) if to is not L.DATETIME else parsed
            return exp.TryCast(this=v, to=target)
        if to is L.BOOLEAN:
            low = tmpl("LOWER(_0)", v)
            return (
                exp.Case()
                .when(exp.In(this=low, expressions=[lit(w) for w in TRUE_WORDS]), exp.Boolean(this=True))
                .when(exp.In(this=low, expressions=[lit(w) for w in FALSE_WORDS]), exp.Boolean(this=False))
            )
    if to is L.TEXT:
        if fmt and src in (L.DATE, L.DATETIME):
            return exp.func("STRFTIME", e, lit(strptime_format(fmt)))
        if src is L.TIME:
            return exp.Cast(this=e, to=target)
        return to_text(e, src, locale)
    if src is L.BOOLEAN and to in NUMERIC_TYPES:
        return exp.Cast(this=exp.Cast(this=e, to=exp.DataType.build("INTEGER")), to=target)
    return exp.TryCast(this=e, to=target)


def is_failure(original: exp.Expr, src: LogicalType, converted: exp.Expr) -> exp.Expr:
    """Row-level condition: a non-blank value that did not convert."""
    present = clean_text(original) if src is L.TEXT else original
    return exp.and_(
        exp.Not(this=exp.Is(this=present, expression=exp.Null())), exp.Is(this=converted, expression=exp.Null())
    )


def supported(src: LogicalType, to: LogicalType) -> bool:
    if to is L.OTHER:
        return False
    if src is L.OTHER:
        return to is L.TEXT
    if src is L.TIME:
        return to in (L.TEXT, L.TIME)
    if to is L.TIME:
        return src in (L.TEXT, L.DATETIME, L.TIME)
    if src is L.BOOLEAN:
        return to in (L.TEXT, L.BOOLEAN, L.INTEGER, L.DECIMAL)
    if to is L.BOOLEAN:
        return src in (L.TEXT, L.BOOLEAN, L.INTEGER)
    if src in (L.DATE, L.DATETIME):
        return to in (L.TEXT, L.DATE, L.DATETIME)
    if to in (L.DATE, L.DATETIME):
        return src in (L.TEXT, L.DATE, L.DATETIME)
    return True
