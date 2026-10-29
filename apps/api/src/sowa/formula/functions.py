"""Single source of truth for the formula function catalog (CLAUDE.md §11).

Each entry carries its pt-BR name, aliases, signature, return type, context,
description, example and the SQLGlot code generator. The catalog is exposed
as-is by `GET /formula/functions`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from typing import TYPE_CHECKING, Literal

import sqlglot
from sqlglot import exp

from sowa.domain.types import NUMERIC_TYPES, TEMPORAL_TYPES, LogicalType, unify

if TYPE_CHECKING:
    from sowa.formula.codegen import GenCtx
    from sowa.formula.typecheck import Typed

L = LogicalType


class P(StrEnum):
    """Parameter type families."""

    ANY = "any"
    TEXT = "text"
    NUMBER = "number"
    INTEGER = "integer"
    BOOL = "boolean"
    DATE = "date"  # date or datetime
    COMPARABLE = "comparable"


P_LABELS: dict[P, str] = {
    P.ANY: "um valor",
    P.TEXT: "um Texto",
    P.NUMBER: "um Número",
    P.INTEGER: "um número inteiro",
    P.BOOL: "uma condição (verdadeiro/falso)",
    P.DATE: "uma Data",
    P.COMPARABLE: "um valor comparável",
}


def accepts(p: P, t: LogicalType) -> bool:
    match p:
        case P.ANY:
            return True
        case P.TEXT:
            return t is L.TEXT
        case P.NUMBER | P.INTEGER:
            return t in NUMERIC_TYPES
        case P.BOOL:
            return t is L.BOOLEAN
        case P.DATE:
            return t in TEMPORAL_TYPES
        case P.COMPARABLE:
            return t is not L.OTHER


@dataclass(frozen=True)
class Param:
    name: str
    type: P
    optional: bool = False
    variadic: bool = False
    literal: bool = False  # must be a literal (e.g. format strings)
    description: str = ""


Codegen = Callable[[list[exp.Expr], "list[Typed]", "GenCtx"], exp.Expr]
ReturnRule = LogicalType | Callable[["list[Typed]"], LogicalType]
Checker = Callable[["list[Typed]"], str | None]


@dataclass(frozen=True)
class FunctionDef:
    name: str
    category: str
    params: tuple[Param, ...]
    returns: ReturnRule
    description: str
    example: str
    codegen: Codegen
    aliases: tuple[str, ...] = ()
    context: Literal["row", "aggregate"] = "row"
    check: Checker | None = None
    excel: bool = True
    returns_label: str = field(default="")

    def signature(self, argsep: str = ";") -> str:
        parts: list[str] = []
        for p in self.params:
            label = p.name + ("..." if p.variadic else "")
            parts.append(f"[{label}]" if p.optional else label)
        return f"{self.name}({argsep.join(parts)})"


# ---------------------------------------------------------------- helpers


@cache
def _parsed_template(sql: str) -> exp.Expr:
    return sqlglot.parse_one(sql, read="duckdb")


_PLACEHOLDER = re.compile(r"^_(\d+)$")


def tmpl(sql: str, *args: exp.Expr) -> exp.Expr:
    """Build an expression from a *static* SQL template with `_0`, `_1`… placeholders.

    User data never goes into the template text: placeholders are substituted
    as AST nodes, so this is still pure AST construction.
    """

    def sub(node: exp.Expr) -> exp.Expr:
        if isinstance(node, exp.Column) and not node.table:
            m = _PLACEHOLDER.match(node.name)
            if m:
                return args[int(m.group(1))].copy()
        return node

    return _parsed_template(sql).copy().transform(sub)


def lit_str(s: str) -> exp.Literal:
    return exp.Literal.string(s)


def lit_num(n: int | float) -> exp.Expr:
    return exp.Literal.number(n)


def as_int(e: exp.Expr, t: LogicalType) -> exp.Expr:
    if t is L.INTEGER:
        return e
    return exp.Cast(this=exp.func("TRUNC", e), to=exp.DataType.build("BIGINT"))


def as_double(e: exp.Expr) -> exp.Expr:
    return exp.Cast(this=e, to=exp.DataType.build("DOUBLE"))


def literal_value(t: Typed) -> str | None:
    from sowa.formula import ast

    node = t.node
    if isinstance(node, ast.StringLit):
        return node.value
    if isinstance(node, ast.NumberLit):
        return node.value
    return None


def same(i: int = 0) -> Callable[[list[Typed]], LogicalType]:
    return lambda args: args[i].type


def numeric_result(args: list[Typed]) -> LogicalType:
    return L.INTEGER if all(a.type is L.INTEGER for a in args) else L.DECIMAL


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.upper())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def to_text(e: exp.Expr, t: LogicalType, locale: str) -> exp.Expr:
    """Convert any value to text the way a pt-BR spreadsheet user expects."""
    if t is L.TEXT:
        return e
    if t is L.BOOLEAN:
        yes, no = ("VERDADEIRO", "FALSO") if locale == "pt-BR" else ("TRUE", "FALSE")
        return exp.Case().when(e, lit_str(yes)).when(exp.Not(this=e), lit_str(no))
    if t is L.DATE:
        fmt = "%d/%m/%Y" if locale == "pt-BR" else "%Y-%m-%d"
        return tmpl(f"STRFTIME(CAST(_0 AS DATE), '{fmt}')", e)
    if t is L.DATETIME:
        fmt = "%d/%m/%Y %H:%M:%S" if locale == "pt-BR" else "%Y-%m-%d %H:%M:%S"
        return tmpl(f"STRFTIME(_0, '{fmt}')", e)
    text = exp.Cast(this=e, to=exp.DataType.build("VARCHAR"))
    if t is L.DECIMAL and locale == "pt-BR":
        return exp.func("REPLACE", text, lit_str("."), lit_str(","))
    return text


def _text_or_empty(e: exp.Expr, t: LogicalType, locale: str) -> exp.Expr:
    return exp.Coalesce(this=to_text(e, t, locale), expressions=[lit_str("")])


# ---------------------------------------------------------------- checks


def _check_branches(args: list[Typed]) -> str | None:
    result = args[1].type
    for a in args[2:]:
        u = unify(result, a.type)
        if u is None:
            return (
                f"Os resultados possíveis precisam ter o mesmo tipo, mas há {_lbl(result)} e {_lbl(a.type)}. "
                "Use TEXTO() ou VALOR() para converter."
            )
        result = u
    return None


def _branches_type(args: list[Typed]) -> LogicalType:
    result = args[1].type
    for a in args[2:]:
        result = unify(result, a.type) or result
    return result


def _check_ses(args: list[Typed]) -> str | None:
    if len(args) % 2 != 0:
        return "SES espera pares de condição e valor: SES(condição1; valor1; condição2; valor2; ...)."
    for i in range(0, len(args), 2):
        if args[i].type is not L.BOOLEAN:
            return (
                f"SES espera uma condição (verdadeiro/falso) no {i + 1}º argumento, mas recebeu {_lbl(args[i].type)}."
            )
    values = [args[i] for i in range(1, len(args), 2)]
    result = values[0].type
    for v in values[1:]:
        u = unify(result, v.type)
        if u is None:
            return f"Os valores de SES precisam ter o mesmo tipo, mas há {_lbl(result)} e {_lbl(v.type)}."
        result = u
    return None


def _ses_type(args: list[Typed]) -> LogicalType:
    values = [args[i] for i in range(1, len(args), 2)]
    result = values[0].type
    for v in values[1:]:
        result = unify(result, v.type) or result
    return result


def _check_same_type(args: list[Typed]) -> str | None:
    result = args[0].type
    for a in args[1:]:
        u = unify(result, a.type)
        if u is None:
            return f"Todos os valores precisam ter o mesmo tipo, mas há {_lbl(result)} e {_lbl(a.type)}."
        result = u
    return None


def _all_type(args: list[Typed]) -> LogicalType:
    result = args[0].type
    for a in args[1:]:
        result = unify(result, a.type) or result
    return result


def _lbl(t: LogicalType) -> str:
    from sowa.domain.types import label

    return label(t)


def _literal_in(index: int, allowed: Sequence[str], fn: str) -> Checker:
    def check(args: list[Typed]) -> str | None:
        if len(args) <= index:
            return None
        v = literal_value(args[index])
        if v is None or v.upper() not in allowed:
            opts = ", ".join(f'"{a}"' if not a.isdigit() else a for a in allowed)
            return f"{fn}: o {index + 1}º argumento precisa ser um destes valores fixos: {opts}."
        return None

    return check


# ---------------------------------------------------------------- codegen pieces


def _se(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    case = exp.Case().when(a[0], a[1])
    return case.else_(a[2]) if len(a) > 2 else case


def _ses(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    case = exp.Case()
    for i in range(0, len(a), 2):
        case = case.when(a[i], a[i + 1])
    return case


def _and(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    out = a[0]
    for x in a[1:]:
        out = exp.And(this=exp.Paren(this=out), expression=exp.Paren(this=x))
    return exp.Paren(this=out)


def _or(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    out = a[0]
    for x in a[1:]:
        out = exp.Or(this=exp.Paren(this=out), expression=exp.Paren(this=x))
    return exp.Paren(this=out)


def _is_blank(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    if t[0].type is L.TEXT:
        return tmpl("(_0 IS NULL OR _0 = '')", a[0])
    return exp.Is(this=a[0], expression=exp.Null())


def _round(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    digits = as_int(a[1], t[1].type) if len(a) > 1 else lit_num(0)
    if t[0].type is L.INTEGER and len(a) == 1:
        return a[0]
    return exp.Round(this=as_double(a[0]), decimals=digits)


def _round_away(up: bool) -> Codegen:
    fn = "CEIL" if up else "FLOOR"

    def gen(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
        digits = as_int(a[1], t[1].type) if len(a) > 1 else lit_num(0)
        return tmpl(f"CAST(SIGN(_0) * {fn}(ABS(_0) * POWER(10, _1)) / POWER(10, _1) AS DOUBLE)", a[0], digits)

    return gen


def _mod(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    c.div_guards.append(a[1])
    expr = tmpl("_0 - _1 * FLOOR(_0 / _1)", a[0], a[1])
    if t[0].type is L.INTEGER and t[1].type is L.INTEGER:
        expr = exp.Cast(this=expr, to=exp.DataType.build("BIGINT"))
    else:
        expr = as_double(expr)
    return exp.Case().when(exp.EQ(this=a[1], expression=lit_num(0)), exp.Null()).else_(expr)


def _guarded(fn_sql: str, cond_sql: str) -> Codegen:
    def gen(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
        return tmpl(f"CASE WHEN {cond_sql} THEN NULL ELSE {fn_sql} END", *a)

    return gen


def _log(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    if len(a) == 1:
        return tmpl("CASE WHEN _0 <= 0 THEN NULL ELSE LOG10(_0) END", a[0])
    return tmpl("CASE WHEN _0 <= 0 OR _1 <= 0 OR _1 = 1 THEN NULL ELSE LN(_0) / LN(_1) END", a[0], a[1])


def _concat(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    parts = [_text_or_empty(x, tt.type, c.locale) for x, tt in zip(a, t, strict=True)]
    out = parts[0]
    for p in parts[1:]:
        out = exp.DPipe(this=out, expression=p)
    return out


def _left(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    n = as_int(a[1], t[1].type) if len(a) > 1 else lit_num(1)
    return exp.func("LEFT", a[0], n)


def _right(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    n = as_int(a[1], t[1].type) if len(a) > 1 else lit_num(1)
    return exp.func("RIGHT", a[0], n)


def _mid(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    return exp.Substring(this=a[0], start=as_int(a[1], t[1].type), length=as_int(a[2], t[2].type))


def _find(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    if len(a) > 2:
        start = as_int(a[2], t[2].type)
        return tmpl(
            "CASE WHEN STRPOS(SUBSTRING(_1, _2), _0) = 0 THEN NULL ELSE STRPOS(SUBSTRING(_1, _2), _0) + _2 - 1 END",
            a[0],
            a[1],
            start,
        )
    return tmpl("NULLIF(STRPOS(_1, _0), 0)", a[0], a[1])


_DATE_TOKENS = [
    ("AAAA", "%Y"),
    ("YYYY", "%Y"),
    ("AA", "%y"),
    ("YY", "%y"),
    ("DD", "%d"),
    ("HH", "%H"),
    ("SS", "%S"),
    ("MMMM", "%B"),
    ("MMM", "%b"),
    ("MM", "%m"),
]


def excel_date_format(fmt: str) -> str:
    """Translate an Excel-style date format (dd/mm/aaaa hh:mm) to strftime."""
    out = ""
    i = 0
    up = fmt.upper()
    after_hour = False
    while i < len(fmt):
        for tok, rep in _DATE_TOKENS:
            if up.startswith(tok, i):
                out += "%M" if tok == "MM" and after_hour else rep
                after_hour = tok == "HH"
                i += len(tok)
                break
        else:
            ch = fmt[i]
            out += "%%" if ch == "%" else ch
            if ch not in ": ":
                after_hour = after_hour and ch == ":"
            i += 1
    return out


_NUM_FMT = re.compile(r"^(?P<prefix>[^#0]*)(?P<int>[#0.,]*?0)(?:(?P<dec>[,.])(?P<frac>0+))?(?P<pct>%?)(?P<suffix>.*)$")


def _text_fmt(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    if len(a) == 1:
        return to_text(a[0], t[0].type, c.locale)
    fmt = literal_value(t[1]) or ""
    src_t = t[0].type
    if src_t in TEMPORAL_TYPES:
        return exp.func("STRFTIME", a[0], lit_str(excel_date_format(fmt)))
    if src_t in NUMERIC_TYPES:
        dec_sep, thou_sep = (",", ".") if c.locale == "pt-BR" else (".", ",")
        m = _NUM_FMT.match(fmt)
        if not m:
            return to_text(a[0], src_t, c.locale)
        int_part = m.group("int") or "0"
        decimals = len(m.group("frac") or "")
        # In pt-BR "0,00" means two decimals; "#.##0" means thousands grouping.
        if m.group("dec") and m.group("dec") != dec_sep:
            decimals = 0
        grouping = thou_sep in int_part
        value = a[0]
        if m.group("pct"):
            value = exp.Mul(this=value, expression=lit_num(100))
        spec = "{:" + ("," if grouping else "") + f".{decimals}f" + "}"
        text: exp.Expr = exp.func("FORMAT", lit_str(spec), as_double(value))
        if c.locale == "pt-BR":
            text = tmpl("REPLACE(REPLACE(REPLACE(_0, ',', '#'), '.', ','), '#', '.')", text)
        prefix, suffix = m.group("prefix"), (m.group("pct") or "") + m.group("suffix")
        parts: list[exp.Expr] = [
            x for x in (lit_str(prefix) if prefix else None, text, lit_str(suffix) if suffix else None) if x is not None
        ]
        out = parts[0]
        for p in parts[1:]:
            out = exp.DPipe(this=out, expression=p)
        return out
    return to_text(a[0], src_t, c.locale)


def _value(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    if c.locale == "pt-BR":
        return tmpl(
            "TRY_CAST(REPLACE(REPLACE(REGEXP_REPLACE(TRIM(_0), '^R\\$\\s*|\\s', '', 'g'), '.', ''), ',', '.')"
            " AS DOUBLE)",
            a[0],
        )
    return tmpl("TRY_CAST(REPLACE(REGEXP_REPLACE(TRIM(_0), '^\\$\\s*|\\s', '', 'g'), ',', '') AS DOUBLE)", a[0])


def _weekday(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    kind = literal_value(t[1]) if len(t) > 1 else "1"
    if kind == "2":
        return tmpl("ISODOW(_0)", a[0])
    if kind == "3":
        return tmpl("ISODOW(_0) - 1", a[0])
    return tmpl("DAYOFWEEK(_0) + 1", a[0])


def _weeknum(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    kind = literal_value(t[1]) if len(t) > 1 else "1"
    if kind == "21":
        return tmpl("WEEKOFYEAR(_0)", a[0])
    offset = "DAYOFWEEK(MAKE_DATE(YEAR(_0), 1, 1))" if kind != "2" else "(ISODOW(MAKE_DATE(YEAR(_0), 1, 1)) - 1)"
    return tmpl(f"CAST(FLOOR((DAYOFYEAR(_0) - 1 + {offset}) / 7) + 1 AS BIGINT)", a[0])


def _datedif(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    unit = (literal_value(t[2]) or "D").upper()
    if unit == "D":
        return tmpl("DATE_DIFF('day', CAST(_0 AS DATE), CAST(_1 AS DATE))", a[0], a[1])
    part = "month" if unit == "M" else "year"
    return tmpl(f"DATE_SUB('{part}', CAST(_0 AS DATE), CAST(_1 AS DATE))", a[0], a[1])


def _networkdays(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    body = (
        "LENGTH(LIST_FILTER(GENERATE_SERIES(CAST(_0 AS TIMESTAMP), CAST(_1 AS TIMESTAMP), INTERVAL 1 DAY), "
        "LAMBDA x : ISODOW(x) < 6))"
    )
    swapped = body.replace("_0", "_X").replace("_1", "_0").replace("_X", "_1")
    return tmpl(f"CASE WHEN CAST(_0 AS DATE) <= CAST(_1 AS DATE) THEN {body} ELSE -{swapped} END", a[0], a[1])


def _try_else(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    return exp.Coalesce(this=exp.func("TRY", a[0]), expressions=[a[1]])


def _sum(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
    s = exp.Sum(this=a[0])
    if t[0].type is L.INTEGER:
        return exp.Cast(this=s, to=exp.DataType.build("BIGINT"))
    return as_double(s)


def _simple(fn: str) -> Codegen:
    def gen(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
        return tmpl(f"{fn}({', '.join(f'_{i}' for i in range(len(a)))})", *a)

    return gen


def _tpl(sql: str) -> Codegen:
    def gen(a: list[exp.Expr], t: list[Typed], c: GenCtx) -> exp.Expr:
        return tmpl(sql, *a)

    return gen


# ---------------------------------------------------------------- catalog

_n = Param("número", P.NUMBER)
_t = Param("texto", P.TEXT)
_d = Param("data", P.DATE)

FUNCTIONS: list[FunctionDef] = [
    # Lógica
    FunctionDef(
        "SE",
        "Lógica",
        (Param("condição", P.BOOL), Param("valor_se_verdadeiro", P.ANY), Param("valor_se_falso", P.ANY, optional=True)),
        _branches_type,
        "Retorna um valor se a condição for verdadeira e outro se for falsa (vazio se omitido).",
        'SE([valor] > 100; "alto"; "baixo")',
        _se,
        aliases=("IF",),
        check=_check_branches,
    ),
    FunctionDef(
        "SES",
        "Lógica",
        (Param("condição", P.BOOL), Param("valor", P.ANY), Param("mais", P.ANY, variadic=True, optional=True)),
        _ses_type,
        "Testa várias condições em ordem e retorna o valor da primeira verdadeira.",
        'SES([nota] >= 9; "A"; [nota] >= 7; "B"; VERDADEIRO; "C")',
        _ses,
        aliases=("IFS",),
        check=_check_ses,
    ),
    FunctionDef(
        "E",
        "Lógica",
        (Param("condição", P.BOOL), Param("mais_condições", P.BOOL, variadic=True, optional=True)),
        L.BOOLEAN,
        "Verdadeiro se todas as condições forem verdadeiras.",
        'E([uf] = "PR"; [valor] > 100)',
        _and,
        aliases=("AND",),
    ),
    FunctionDef(
        "OU",
        "Lógica",
        (Param("condição", P.BOOL), Param("mais_condições", P.BOOL, variadic=True, optional=True)),
        L.BOOLEAN,
        "Verdadeiro se pelo menos uma condição for verdadeira.",
        'OU([uf] = "PR"; [uf] = "SC")',
        _or,
        aliases=("OR",),
    ),
    FunctionDef(
        "NÃO",
        "Lógica",
        (Param("condição", P.BOOL),),
        L.BOOLEAN,
        "Inverte uma condição.",
        "NÃO(ÉNULO([email]))",
        lambda a, t, c: exp.Not(this=exp.Paren(this=a[0])),
        aliases=("NOT",),
    ),
    FunctionDef(
        "SEERRO",
        "Lógica",
        (Param("valor", P.ANY), Param("valor_se_erro", P.ANY)),
        _all_type,
        "Retorna o segundo valor se o primeiro der erro ou ficar vazio (ex.: divisão por zero).",
        "SEERRO([receita] / [quantidade]; 0)",
        _try_else,
        aliases=("IFERROR",),
        check=_check_same_type,
    ),
    FunctionDef(
        "ÉNULO",
        "Lógica",
        (Param("valor", P.ANY),),
        L.BOOLEAN,
        "Verdadeiro se o valor estiver vazio (nulo, ou texto vazio).",
        "ÉNULO([email])",
        _is_blank,
        aliases=("ISBLANK", "ÉCÉL.VAZIA", "ISNULL"),
    ),
    FunctionDef(
        "SENULO",
        "Lógica",
        (Param("valor", P.ANY), Param("alternativas", P.ANY, variadic=True)),
        _all_type,
        "Retorna o primeiro valor que não estiver vazio.",
        'SENULO([telefone]; [celular]; "sem contato")',
        lambda a, t, c: exp.Coalesce(this=a[0], expressions=a[1:]),
        aliases=("COALESCE", "IFNULL"),
        check=_check_same_type,
        excel=False,
    ),
    # Matemática
    FunctionDef(
        "ARRED",
        "Matemática",
        (_n, Param("casas", P.INTEGER, optional=True)),
        lambda a: L.INTEGER if a[0].type is L.INTEGER and len(a) == 1 else L.DECIMAL,
        "Arredonda um número para a quantidade de casas decimais indicada.",
        "ARRED([valor] * 1,5; 2)",
        _round,
        aliases=("ROUND",),
    ),
    FunctionDef(
        "ARREDONDAR.PARA.CIMA",
        "Matemática",
        (_n, Param("casas", P.INTEGER, optional=True)),
        L.DECIMAL,
        "Arredonda para longe do zero.",
        "ARREDONDAR.PARA.CIMA([valor]; 0)",
        _round_away(True),
        aliases=("ROUNDUP",),
    ),
    FunctionDef(
        "ARREDONDAR.PARA.BAIXO",
        "Matemática",
        (_n, Param("casas", P.INTEGER, optional=True)),
        L.DECIMAL,
        "Arredonda em direção ao zero (trunca).",
        "ARREDONDAR.PARA.BAIXO([valor]; 1)",
        _round_away(False),
        aliases=("ROUNDDOWN",),
    ),
    FunctionDef("ABS", "Matemática", (_n,), same(), "Valor absoluto.", "ABS([saldo])", _simple("ABS")),
    FunctionDef(
        "INT",
        "Matemática",
        (_n,),
        L.INTEGER,
        "Arredonda para baixo até o inteiro mais próximo.",
        "INT([idade_anos])",
        _tpl("CAST(FLOOR(_0) AS BIGINT)"),
    ),
    FunctionDef(
        "MOD",
        "Matemática",
        (Param("número", P.NUMBER), Param("divisor", P.NUMBER)),
        numeric_result,
        "Resto da divisão (com o sinal do divisor, como no Excel).",
        "MOD([linha]; 2)",
        _mod,
    ),
    FunctionDef(
        "POTÊNCIA",
        "Matemática",
        (Param("base", P.NUMBER), Param("expoente", P.NUMBER)),
        L.DECIMAL,
        "Eleva um número a uma potência.",
        "POTÊNCIA(1,1; 12)",
        _tpl("POWER(_0, _1)"),
        aliases=("POWER",),
    ),
    FunctionDef(
        "RAIZ",
        "Matemática",
        (_n,),
        L.DECIMAL,
        "Raiz quadrada (vazio para números negativos).",
        "RAIZ([área])",
        _guarded("SQRT(_0)", "_0 < 0"),
        aliases=("SQRT",),
    ),
    FunctionDef(
        "LOG",
        "Matemática",
        (_n, Param("base", P.NUMBER, optional=True)),
        L.DECIMAL,
        "Logaritmo na base indicada (10 se omitida).",
        "LOG([valor]; 2)",
        _log,
    ),
    FunctionDef(
        "LN",
        "Matemática",
        (_n,),
        L.DECIMAL,
        "Logaritmo natural.",
        "LN([valor])",
        _guarded("LN(_0)", "_0 <= 0"),
    ),
    FunctionDef("EXP", "Matemática", (_n,), L.DECIMAL, "e elevado à potência indicada.", "EXP(1)", _simple("EXP")),
    # Texto
    FunctionDef(
        "CONCAT",
        "Texto",
        (Param("valor", P.ANY), Param("mais_valores", P.ANY, variadic=True, optional=True)),
        L.TEXT,
        "Junta vários valores em um texto (vazios viram texto vazio).",
        'CONCAT([nome]; " "; [sobrenome])',
        _concat,
        aliases=("CONCATENATE", "CONCATENAR"),
    ),
    FunctionDef(
        "ESQUERDA",
        "Texto",
        (_t, Param("núm_caract", P.INTEGER, optional=True)),
        L.TEXT,
        "Primeiros caracteres de um texto.",
        "ESQUERDA([cep]; 5)",
        _left,
        aliases=("LEFT",),
    ),
    FunctionDef(
        "DIREITA",
        "Texto",
        (_t, Param("núm_caract", P.INTEGER, optional=True)),
        L.TEXT,
        "Últimos caracteres de um texto.",
        "DIREITA([cpf]; 2)",
        _right,
        aliases=("RIGHT",),
    ),
    FunctionDef(
        "EXT.TEXTO",
        "Texto",
        (_t, Param("início", P.INTEGER), Param("núm_caract", P.INTEGER)),
        L.TEXT,
        "Parte do meio de um texto.",
        "EXT.TEXTO([código]; 3; 4)",
        _mid,
        aliases=("MID",),
    ),
    FunctionDef(
        "NÚM.CARACT",
        "Texto",
        (_t,),
        L.INTEGER,
        "Quantidade de caracteres.",
        "NÚM.CARACT([descrição])",
        _simple("LENGTH"),
        aliases=("LEN",),
    ),
    FunctionDef(
        "MAIÚSCULA",
        "Texto",
        (_t,),
        L.TEXT,
        "Tudo em maiúsculas.",
        "MAIÚSCULA([uf])",
        _simple("UPPER"),
        aliases=("UPPER",),
    ),
    FunctionDef(
        "MINÚSCULA",
        "Texto",
        (_t,),
        L.TEXT,
        "Tudo em minúsculas.",
        "MINÚSCULA([email])",
        _simple("LOWER"),
        aliases=("LOWER",),
    ),
    FunctionDef(
        "PRI.MAIÚSCULA",
        "Texto",
        (_t,),
        L.TEXT,
        "Primeira letra de cada palavra em maiúscula.",
        "PRI.MAIÚSCULA([nome])",
        _tpl("ARRAY_TO_STRING(LIST_TRANSFORM(STR_SPLIT(LOWER(_0), ' '), LAMBDA w : UPPER(w[1]) || w[2:]), ' ')"),
        aliases=("PROPER",),
    ),
    FunctionDef(
        "ARRUMAR",
        "Texto",
        (_t,),
        L.TEXT,
        "Remove espaços do início e do fim e espaços repetidos no meio.",
        "ARRUMAR([nome])",
        _tpl("TRIM(REGEXP_REPLACE(_0, '\\s+', ' ', 'g'))"),
        aliases=("TRIM",),
    ),
    FunctionDef(
        "SUBSTITUIR",
        "Texto",
        (_t, Param("texto_antigo", P.TEXT), Param("novo_texto", P.TEXT)),
        L.TEXT,
        "Troca todas as ocorrências de um trecho por outro.",
        'SUBSTITUIR([telefone]; "-"; "")',
        _simple("REPLACE"),
        aliases=("SUBSTITUTE",),
    ),
    FunctionDef(
        "PROCURAR",
        "Texto",
        (Param("texto_procurado", P.TEXT), Param("no_texto", P.TEXT), Param("início", P.INTEGER, optional=True)),
        L.INTEGER,
        "Posição de um trecho dentro do texto (diferencia maiúsculas; vazio se não achar).",
        'PROCURAR("@"; [email])',
        _find,
        aliases=("FIND",),
    ),
    FunctionDef(
        "TEXTO",
        "Texto",
        (Param("valor", P.ANY), Param("formato", P.TEXT, optional=True, literal=True)),
        L.TEXT,
        'Converte um valor em texto, com formato opcional (ex.: "dd/mm/aaaa", "#.##0,00", "0%").',
        'TEXTO([data_venda]; "dd/mm/aaaa")',
        _text_fmt,
        aliases=("TEXT",),
    ),
    FunctionDef(
        "VALOR",
        "Texto",
        (_t,),
        L.DECIMAL,
        'Converte texto em número (aceita "1.234,56" e "R$ 10,00").',
        'VALOR("1.234,56")',
        _value,
        aliases=("VALUE",),
    ),
    # Data
    FunctionDef("HOJE", "Data", (), L.DATE, "Data de hoje.", "HOJE()", _tpl("CURRENT_DATE"), aliases=("TODAY",)),
    FunctionDef(
        "AGORA",
        "Data",
        (),
        L.DATETIME,
        "Data e hora atuais.",
        "AGORA()",
        _tpl("CAST(CURRENT_TIMESTAMP AS TIMESTAMP)"),
        aliases=("NOW",),
    ),
    FunctionDef(
        "DATA",
        "Data",
        (Param("ano", P.INTEGER), Param("mês", P.INTEGER), Param("dia", P.INTEGER)),
        L.DATE,
        "Monta uma data (meses e dias excedentes avançam, como no Excel).",
        "DATA(2025; 12; 31)",
        lambda a, t, c: tmpl(
            "CAST(MAKE_DATE(_0, 1, 1) + TO_MONTHS(CAST(_1 AS INTEGER) - 1) + TO_DAYS(CAST(_2 AS INTEGER) - 1) AS DATE)",
            as_int(a[0], t[0].type),
            as_int(a[1], t[1].type),
            as_int(a[2], t[2].type),
        ),
        aliases=("DATE",),
    ),
    FunctionDef(
        "ANO", "Data", (_d,), L.INTEGER, "Ano de uma data.", "ANO([data_venda])", _simple("YEAR"), aliases=("YEAR",)
    ),
    FunctionDef(
        "MÊS",
        "Data",
        (_d,),
        L.INTEGER,
        "Mês de uma data (1 a 12).",
        "MÊS([data_venda])",
        _simple("MONTH"),
        aliases=("MONTH",),
    ),
    FunctionDef("DIA", "Data", (_d,), L.INTEGER, "Dia do mês.", "DIA([data_venda])", _simple("DAY"), aliases=("DAY",)),
    FunctionDef(
        "DIA.DA.SEMANA",
        "Data",
        (_d, Param("tipo", P.INTEGER, optional=True, literal=True)),
        L.INTEGER,
        "Dia da semana. Tipo 1: domingo=1 (padrão); 2: segunda=1; 3: segunda=0.",
        "DIA.DA.SEMANA([data]; 2)",
        _weekday,
        aliases=("WEEKDAY",),
        check=_literal_in(1, ("1", "2", "3"), "DIA.DA.SEMANA"),
    ),
    FunctionDef(
        "NÚMSEMANA",
        "Data",
        (_d, Param("tipo", P.INTEGER, optional=True, literal=True)),
        L.INTEGER,
        "Número da semana no ano. Tipo 1: semana começa no domingo (padrão); 2: segunda; 21: ISO.",
        "NÚMSEMANA([data])",
        _weeknum,
        aliases=("WEEKNUM",),
        check=_literal_in(1, ("1", "2", "21"), "NÚMSEMANA"),
    ),
    FunctionDef(
        "FIMMÊS",
        "Data",
        (_d, Param("meses", P.INTEGER)),
        L.DATE,
        "Último dia do mês, avançando ou recuando meses.",
        "FIMMÊS([data]; 0)",
        lambda a, t, c: tmpl(
            "LAST_DAY(CAST(_0 AS DATE) + TO_MONTHS(CAST(_1 AS INTEGER)))", a[0], as_int(a[1], t[1].type)
        ),
        aliases=("EOMONTH",),
    ),
    FunctionDef(
        "DATAM",
        "Data",
        (_d, Param("meses", P.INTEGER)),
        L.DATE,
        "Soma (ou subtrai) meses a uma data.",
        "DATAM([data]; -1)",
        lambda a, t, c: tmpl(
            "CAST(CAST(_0 AS DATE) + TO_MONTHS(CAST(_1 AS INTEGER)) AS DATE)", a[0], as_int(a[1], t[1].type)
        ),
        aliases=("EDATE",),
    ),
    FunctionDef(
        "DATADIF",
        "Data",
        (Param("data_inicial", P.DATE), Param("data_final", P.DATE), Param("unidade", P.TEXT, literal=True)),
        L.INTEGER,
        'Diferença entre datas em dias ("D"), meses completos ("M") ou anos completos ("Y").',
        'DATADIF([nascimento]; HOJE(); "Y")',
        _datedif,
        aliases=("DATEDIF",),
        check=_literal_in(2, ("D", "M", "Y"), "DATADIF"),
    ),
    FunctionDef(
        "DIATRABALHOTOTAL",
        "Data",
        (Param("data_inicial", P.DATE), Param("data_final", P.DATE)),
        L.INTEGER,
        "Dias úteis (segunda a sexta) entre duas datas, inclusive.",
        "DIATRABALHOTOTAL([abertura]; [fechamento])",
        _networkdays,
        aliases=("NETWORKDAYS",),
    ),
    # Extensões
    FunctionDef(
        "TRIMESTRE",
        "Data",
        (_d,),
        L.INTEGER,
        "Trimestre do ano (1 a 4).",
        "TRIMESTRE([data_venda])",
        _simple("QUARTER"),
        aliases=("QUARTER",),
        excel=False,
    ),
    FunctionDef(
        "CONTÉM",
        "Texto",
        (_t, Param("trecho", P.TEXT)),
        L.BOOLEAN,
        "Verdadeiro se o texto contém o trecho (diferencia maiúsculas).",
        'CONTÉM([produto]; "Kit")',
        _simple("CONTAINS"),
        aliases=("CONTAINS",),
        excel=False,
    ),
    FunctionDef(
        "COMEÇACOM",
        "Texto",
        (_t, Param("início", P.TEXT)),
        L.BOOLEAN,
        "Verdadeiro se o texto começa com o trecho.",
        'COMEÇACOM([cep]; "80")',
        _simple("STARTS_WITH"),
        aliases=("STARTSWITH",),
        excel=False,
    ),
    FunctionDef(
        "TERMINACOM",
        "Texto",
        (_t, Param("fim", P.TEXT)),
        L.BOOLEAN,
        "Verdadeiro se o texto termina com o trecho.",
        'TERMINACOM([email]; ".br")',
        _simple("ENDS_WITH"),
        aliases=("ENDSWITH",),
        excel=False,
    ),
    FunctionDef(
        "REGEX.EXTRAIR",
        "Texto",
        (_t, Param("padrão", P.TEXT), Param("grupo", P.INTEGER, optional=True)),
        L.TEXT,
        "Extrai o trecho que casa com a expressão regular.",
        'REGEX.EXTRAIR([texto]; "\\d+")',
        lambda a, t, c: exp.func("REGEXP_EXTRACT", a[0], a[1], *([as_int(a[2], t[2].type)] if len(a) > 2 else [])),
        aliases=("REGEXEXTRACT",),
        excel=False,
    ),
    FunctionDef(
        "REGEX.SUBSTITUIR",
        "Texto",
        (_t, Param("padrão", P.TEXT), Param("novo_texto", P.TEXT)),
        L.TEXT,
        "Substitui todas as ocorrências da expressão regular.",
        'REGEX.SUBSTITUIR([cpf]; "[^0-9]"; "")',
        _tpl("REGEXP_REPLACE(_0, _1, _2, 'g')"),
        aliases=("REGEXREPLACE",),
        excel=False,
    ),
    FunctionDef(
        "REMOVER.ACENTOS",
        "Texto",
        (_t,),
        L.TEXT,
        "Remove acentos (ação → acao).",
        "REMOVER.ACENTOS([cidade])",
        _simple("STRIP_ACCENTS"),
        aliases=("UNACCENT",),
        excel=False,
    ),
    # Agregação
    FunctionDef(
        "SOMA",
        "Agregação",
        (_n,),
        same(),
        "Soma dos valores do grupo.",
        "SOMA([receita])",
        _sum,
        aliases=("SUM",),
        context="aggregate",
    ),
    FunctionDef(
        "MÉDIA",
        "Agregação",
        (_n,),
        L.DECIMAL,
        "Média dos valores do grupo.",
        "MÉDIA([preço])",
        _simple("AVG"),
        aliases=("AVERAGE", "AVG"),
        context="aggregate",
    ),
    FunctionDef(
        "CONT.VALORES",
        "Agregação",
        (Param("valor", P.ANY),),
        L.INTEGER,
        "Quantidade de valores não vazios no grupo.",
        "CONT.VALORES([pedido])",
        _simple("COUNT"),
        aliases=("COUNTA",),
        context="aggregate",
    ),
    FunctionDef(
        "CONT.DISTINTO",
        "Agregação",
        (Param("valor", P.ANY),),
        L.INTEGER,
        "Quantidade de valores distintos no grupo.",
        "CONT.DISTINTO([cliente])",
        _tpl("COUNT(DISTINCT _0)"),
        aliases=("COUNTDISTINCT",),
        context="aggregate",
        excel=False,
    ),
    FunctionDef(
        "CONT.LINHAS",
        "Agregação",
        (),
        L.INTEGER,
        "Quantidade de linhas no grupo.",
        "CONT.LINHAS()",
        _tpl("COUNT(*)"),
        aliases=("COUNTROWS",),
        context="aggregate",
        excel=False,
    ),
    FunctionDef(
        "MÁXIMO",
        "Agregação",
        (Param("valor", P.COMPARABLE),),
        same(),
        "Maior valor do grupo.",
        "MÁXIMO([data_venda])",
        _simple("MAX"),
        aliases=("MAX",),
        context="aggregate",
    ),
    FunctionDef(
        "MÍNIMO",
        "Agregação",
        (Param("valor", P.COMPARABLE),),
        same(),
        "Menor valor do grupo.",
        "MÍNIMO([preço])",
        _simple("MIN"),
        aliases=("MIN",),
        context="aggregate",
    ),
    FunctionDef(
        "MED",
        "Agregação",
        (_n,),
        L.DECIMAL,
        "Mediana dos valores do grupo.",
        "MED([tempo])",
        _tpl("CAST(MEDIAN(_0) AS DOUBLE)"),
        aliases=("MEDIAN",),
        context="aggregate",
    ),
    FunctionDef(
        "DESVPAD",
        "Agregação",
        (_n,),
        L.DECIMAL,
        "Desvio padrão (amostral) dos valores do grupo.",
        "DESVPAD([valor])",
        _simple("STDDEV_SAMP"),
        aliases=("STDEV",),
        context="aggregate",
    ),
]


@cache
def _index() -> dict[str, FunctionDef]:
    idx: dict[str, FunctionDef] = {}
    for f in FUNCTIONS:
        for n in (f.name, *f.aliases):
            idx[_norm(n)] = f
    return idx


def lookup(name: str) -> FunctionDef | None:
    return _index().get(_norm(name))


def suggest(name: str) -> str | None:
    """Closest function name, for 'did you mean' hints."""
    import difflib

    keys = list(_index())
    match = difflib.get_close_matches(_norm(name), keys, n=1, cutoff=0.6)
    return _index()[match[0]].name if match else None
