"""Parsing of user-typed literal values (filter rules, replacements…) per column type."""

from __future__ import annotations

import re
from datetime import date, datetime, time

from sqlglot import exp

from forja.domain.types import LogicalType, label
from forja.nodes._convert import FALSE_WORDS, TRUE_WORDS
from forja.nodes.base import lit

L = LogicalType
Scalar = str | int | float | bool | None


class ValueError_(Exception):  # noqa: N801 - avoid shadowing builtin ValueError
    pass


_BR_NUMBER = re.compile(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$|^-?\d+(,\d+)?$")
_US_NUMBER = re.compile(r"^-?\d{1,3}(,\d{3})*(\.\d+)?$|^-?\d+(\.\d+)?$")


def parse_number(raw: Scalar, locale: str = "pt-BR") -> float | int:
    if isinstance(raw, bool) or raw is None:
        raise ValueError_("não é um número")
    if isinstance(raw, (int, float)):
        return raw
    s = raw.strip().removeprefix("R$").strip().replace(" ", "")
    if locale == "pt-BR" and _BR_NUMBER.match(s):
        s = s.replace(".", "").replace(",", ".")
    elif _US_NUMBER.match(s):
        s = s.replace(",", "")
    else:
        raise ValueError_("não é um número")
    f = float(s)
    return int(f) if f.is_integer() and "." not in s else f


def parse_date(raw: Scalar) -> date:
    if not isinstance(raw, str):
        raise ValueError_("não é uma data")
    s = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError_("não é uma data (use dd/mm/aaaa)")


def parse_datetime(raw: Scalar) -> datetime:
    if not isinstance(raw, str):
        raise ValueError_("não é data e hora")
    s = raw.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError_("não é data e hora (use dd/mm/aaaa hh:mm)")


def parse_time(raw: Scalar) -> time:
    if not isinstance(raw, str):
        raise ValueError_("não é uma hora")
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw.strip(), fmt).time()
        except ValueError:
            continue
    raise ValueError_("não é uma hora (use hh:mm)")


def parse_bool(raw: Scalar) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        raise ValueError_("não é verdadeiro/falso")
    s = str(raw).strip().lower()
    if s in TRUE_WORDS:
        return True
    if s in FALSE_WORDS:
        return False
    raise ValueError_("não é verdadeiro/falso")


def typed_literal(raw: Scalar, t: LogicalType, locale: str = "pt-BR") -> exp.Expr:
    """SQL literal for `raw` interpreted as type `t`. Raises ValueError_ with a pt-BR reason."""
    if raw is None:
        return exp.Null()
    match t:
        case L.INTEGER | L.DECIMAL:
            return lit(parse_number(raw, locale))
        case L.DATE:
            return exp.Cast(this=lit(parse_date(raw).isoformat()), to=exp.DataType.build("DATE"))
        case L.DATETIME:
            return exp.Cast(this=lit(parse_datetime(raw).isoformat(sep=" ")), to=exp.DataType.build("TIMESTAMP"))
        case L.TIME:
            return exp.Cast(this=lit(parse_time(raw).isoformat()), to=exp.DataType.build("TIME"))
        case L.BOOLEAN:
            return exp.Boolean(this=parse_bool(raw))
        case _:
            return lit(str(raw))


def value_error_message(column: str, raw: Scalar, t: LogicalType, reason: str) -> str:
    return f'O valor "{raw}" para a coluna "{column}" ({label(t)}) {reason}.'
