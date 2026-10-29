"""Formula language: text -> type -> result, both locales, nulls, errors with positions."""

from __future__ import annotations

import datetime as dt
from typing import Any

import duckdb
import pytest

from sowa.domain.issues import IssueCode
from sowa.domain.schema import Schema
from sowa.domain.types import LogicalType as L
from sowa.domain.types import from_duckdb
from sowa.formula.parser import parse
from sowa.formula.render import render
from sowa.formula.service import compile_formula
from sowa.formula.typecheck import FormulaError

SCHEMA = Schema.of(
    ("preço", L.DECIMAL),
    ("quantidade", L.INTEGER),
    ("nome", L.TEXT),
    ("data", L.DATE),
    ("uf", L.TEXT),
    ("ativo", L.BOOLEAN),
    ("Nome Completo", L.TEXT),
    ("momento", L.DATETIME),
)
ROWS = """
SELECT * FROM (VALUES
  (10.5::DOUBLE, 3::BIGINT, '  joão   da silva ', DATE '2025-02-10', 'pr', true, 'Ana Lima',
   TIMESTAMP '2025-02-10 08:30:00'),
  (2.0::DOUBLE, 0::BIGINT, NULL, DATE '2025-12-31', 'SC', false, NULL, NULL)
) t("preço", quantidade, nome, data, uf, ativo, "Nome Completo", momento)
"""


@pytest.fixture(scope="module")
def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute(f"CREATE TABLE t AS {ROWS}")
    return c


def evaluate(con: duckdb.DuckDBPyConnection, formula: str, locale: str = "pt-BR") -> tuple[L, L, list[Any]]:
    f = compile_formula(formula, SCHEMA, locale=locale)  # type: ignore[arg-type]
    sql = f.sql.sql(dialect="duckdb", identify=True)
    values = [r[0] for r in con.sql(f"SELECT {sql} FROM t").fetchall()]
    actual = from_duckdb(con.execute(f"SELECT typeof({sql}) FROM t LIMIT 1").fetchall()[0][0])
    return f.type, actual, values


CASES: list[tuple[str, L, list[Any]]] = [
    ("[preço] * [quantidade]", L.DECIMAL, [31.5, 0.0]),
    ("[quantidade] * 2", L.INTEGER, [6, 0]),
    ("[preço] / [quantidade]", L.DECIMAL, [3.5, None]),  # division by zero -> null
    ("SEERRO([preço] / [quantidade]; 0)", L.DECIMAL, [3.5, 0.0]),
    ("1,5 + 1", L.DECIMAL, [2.5, 2.5]),
    ("-2^2", L.DECIMAL, [4.0, 4.0]),  # Excel: negation binds tighter than ^
    ("10%", L.DECIMAL, [0.1, 0.1]),
    ('SE([uf] = "PR"; "Paraná"; "Outro")', L.TEXT, ["Paraná", "Outro"]),  # case-insensitive text compare
    ("SE([quantidade] > 0; [preço])", L.DECIMAL, [10.5, None]),
    ('SES([quantidade] > 2; "muitos"; [quantidade] > 0; "pouco"; VERDADEIRO; "nada")', L.TEXT, ["muitos", "nada"]),
    ('"R$ " & [preço]', L.TEXT, ["R$ 10,5", "R$ 2,0"]),
    ('[nome] & "!"', L.TEXT, ["  joão   da silva !", "!"]),  # & treats null as empty text
    ('"Data: " & [data]', L.TEXT, ["Data: 10/02/2025", "Data: 31/12/2025"]),
    ('CONCAT([uf]; "-"; [quantidade])', L.TEXT, ["pr-3", "SC-0"]),
    ("PRI.MAIÚSCULA(ARRUMAR([nome]))", L.TEXT, ["João Da Silva", None]),
    ("MAIUSCULA([uf])", L.TEXT, ["PR", "SC"]),  # accents optional in function names
    ("NÚM.CARACT([uf])", L.INTEGER, [2, 2]),
    ("ESQUERDA([Nome Completo]; 3)", L.TEXT, ["Ana", None]),
    ("DIREITA([uf])", L.TEXT, ["r", "C"]),
    ('EXT.TEXTO("abcdef"; 2; 3)', L.TEXT, ["bcd", "bcd"]),
    ('SUBSTITUIR([uf]; "p"; "P")', L.TEXT, ["Pr", "SC"]),
    ('PROCURAR("r"; [uf])', L.INTEGER, [2, None]),
    ('TEXTO([preço] * 1000; "#.##0,00")', L.TEXT, ["10.500,00", "2.000,00"]),
    ('TEXTO([data]; "dd/mm/aaaa")', L.TEXT, ["10/02/2025", "31/12/2025"]),
    ('TEXTO(0,256; "0,0%")', L.TEXT, ["25,6%", "25,6%"]),
    ('VALOR("R$ 1.234,56")', L.DECIMAL, [1234.56, 1234.56]),
    ("ARRED([preço] * 1,5; 2)", L.DECIMAL, [15.75, 3.0]),
    ("ARREDONDAR.PARA.CIMA(2,341; 2)", L.DECIMAL, [2.35, 2.35]),
    ("ARREDONDAR.PARA.BAIXO(-2,349; 2)", L.DECIMAL, [-2.34, -2.34]),
    ("INT(-2,5)", L.INTEGER, [-3, -3]),
    ("MOD(-7; 3)", L.INTEGER, [2, 2]),
    ("MOD(5; [quantidade])", L.INTEGER, [2, None]),
    ("RAIZ(-4)", L.DECIMAL, [None, None]),
    ("LOG(8; 2)", L.DECIMAL, [3.0, 3.0]),
    ("ABS(-[quantidade])", L.INTEGER, [3, 0]),
    ("DATA(2025; 13; 32)", L.DATE, [dt.date(2026, 2, 1)] * 2),  # Excel-style overflow
    ("ANO([data]) * 100 + MÊS([data])", L.INTEGER, [202502, 202512]),
    ("DIA([momento])", L.INTEGER, [10, None]),
    ("FIMMÊS([data]; 1)", L.DATE, [dt.date(2025, 3, 31), dt.date(2026, 1, 31)]),
    ("DATAM([data]; -1)", L.DATE, [dt.date(2025, 1, 10), dt.date(2025, 11, 30)]),
    ('DATADIF([data]; DATA(2026; 3; 1); "M")', L.INTEGER, [12, 2]),
    ('DATADIF(DATA(2000; 6; 15); [data]; "Y")', L.INTEGER, [24, 25]),
    ("DIA.DA.SEMANA([data])", L.INTEGER, [2, 4]),  # 10/02/2025 = segunda; 31/12/2025 = quarta
    ("DIA.DA.SEMANA([data]; 2)", L.INTEGER, [1, 3]),
    ("NÚMSEMANA([data])", L.INTEGER, [7, 53]),
    ("TRIMESTRE([data])", L.INTEGER, [1, 4]),
    ("[data] + 30", L.DATE, [dt.date(2025, 3, 12), dt.date(2026, 1, 30)]),
    ("[data] - DATA(2025; 1; 1)", L.INTEGER, [40, 364]),
    ("DIATRABALHOTOTAL([data]; [data] + 14)", L.INTEGER, [11, 11]),
    ('E([quantidade] > 0; NÃO([uf] = "sc"))', L.BOOLEAN, [True, False]),
    ("OU([ativo]; [quantidade] = 0)", L.BOOLEAN, [True, True]),
    ("ÉNULO([nome])", L.BOOLEAN, [False, True]),
    ('SENULO([nome]; "—")', L.TEXT, ["  joão   da silva ", "—"]),
    ('CONTÉM([Nome Completo]; "Lima")', L.BOOLEAN, [True, None]),
    ('COMEÇACOM([uf]; "S")', L.BOOLEAN, [False, True]),
    ('REGEX.EXTRAIR("pedido 123"; "\\d+")', L.TEXT, ["123", "123"]),
    ('REGEX.SUBSTITUIR("123.456.789-00"; "[^0-9]"; "")', L.TEXT, ["12345678900"] * 2),
    ('REMOVER.ACENTOS("Ação São João")', L.TEXT, ["Acao Sao Joao"] * 2),
    ("[ativo] = VERDADEIRO", L.BOOLEAN, [True, False]),
]


@pytest.mark.parametrize(("formula", "expected_type", "expected"), CASES, ids=[c[0] for c in CASES])
def test_formula_ptbr(con: duckdb.DuckDBPyConnection, formula: str, expected_type: L, expected: list[Any]) -> None:
    static, actual, values = evaluate(con, formula)
    assert static == expected_type
    assert actual == expected_type, "static type must match the engine's type"
    assert (
        [float(v) if isinstance(v, float) else v for v in values] == pytest.approx(expected)
        if all(isinstance(x, (int, float)) or x is None for x in expected)
        else values == expected
    )


EN_CASES = [
    ("IF([quantidade] > 0, ROUND([preço] * 1.5, 1), 0)", L.DECIMAL, [15.8, 0.0]),
    ('CONCATENATE([uf], "-", TEXT([preço], "0.00"))', L.TEXT, ["pr-10.50", "SC-2.00"]),
    ("SE([quantidade] > 0; 1; 2)", None, None),  # pt-BR separators are a syntax error in en-US
]


@pytest.mark.parametrize(("formula", "expected_type", "expected"), EN_CASES)
def test_formula_en_us(
    con: duckdb.DuckDBPyConnection, formula: str, expected_type: L | None, expected: list[Any] | None
) -> None:
    if expected_type is None:
        with pytest.raises(FormulaError) as e:
            compile_formula(formula, SCHEMA, locale="en-US")
        assert e.value.code is IssueCode.FORMULA_SYNTAX
        return
    static, actual, values = evaluate(con, formula, "en-US")
    assert static == actual == expected_type
    assert values == expected


ERRORS = [
    ('[preço] + "a"', IssueCode.FORMULA_TYPE, (0, 13), "&"),
    ("SE([preço]; 1; 2)", IssueCode.FORMULA_TYPE, (3, 10), "uma condição"),
    ("SOMA([preço])", IssueCode.FORMULA_CONTEXT, (0, 4), "Agrupar"),
    ("ESQUERDA([nome])x", IssueCode.FORMULA_SYNTAX, (16, 17), "operador"),
    ("ARRED([preço], 2)", IssueCode.FORMULA_SYNTAX, (13, 14), "separe argumentos"),
    ("[preco] * 2", IssueCode.COLUMN_NOT_FOUND, (0, 7), "[preço]"),
    ("FOO(1)", IssueCode.FORMULA_UNKNOWN_FUNCTION, (0, 3), "não existe"),
    ("SOMAA(1)", IssueCode.FORMULA_UNKNOWN_FUNCTION, (0, 5), "SOMA"),
    ('SE(1 > 0; 1; "a")', IssueCode.FORMULA_TYPE, (0, 17), "mesmo tipo"),
    ("(1 + 2", IssueCode.FORMULA_SYNTAX, (5, 6), "parêntese"),
    ("ESQUERDA()", IssueCode.FORMULA_ARGUMENTS, (0, 10), "ESQUERDA(texto"),
    ("[nome] * 2", IssueCode.FORMULA_TYPE, (0, 10), "VALOR"),
    ("ANO([nome])", IssueCode.FORMULA_TYPE, (4, 10), "Alterar tipo"),
    ("TEXTO([preço]; [nome])", IssueCode.FORMULA_ARGUMENTS, (15, 21), "valor fixo"),
    ('DATADIF([data]; [data]; "X")', IssueCode.FORMULA_TYPE, (0, 28), '"D"'),
    ("nome", IssueCode.FORMULA_SYNTAX, (0, 4), "[nome]"),
    ("", IssueCode.FORMULA_SYNTAX, (0, 0), "vazia"),
    ("'texto'", IssueCode.FORMULA_SYNTAX, (0, 1), "aspas duplas"),
]


@pytest.mark.parametrize(("formula", "code", "pos", "fragment"), ERRORS, ids=[e[0] or "<vazia>" for e in ERRORS])
def test_formula_errors(formula: str, code: IssueCode, pos: tuple[int, int], fragment: str) -> None:
    with pytest.raises(FormulaError) as e:
        compile_formula(formula, SCHEMA)
    assert e.value.code is code
    assert (e.value.start, e.value.end) == pos
    assert fragment in e.value.message


def test_aggregate_context() -> None:
    f = compile_formula("SOMA([preço]) / SOMA([quantidade])", SCHEMA, context="aggregate")
    assert f.type is L.DECIMAL
    assert f.is_aggregate
    with pytest.raises(FormulaError) as e:
        compile_formula("[preço] * 2", SCHEMA, context="aggregate")
    assert e.value.code is IssueCode.FORMULA_CONTEXT
    ok = compile_formula('[uf] & ": " & SOMA([quantidade])', SCHEMA, context="aggregate", group_keys=["uf"])
    assert ok.type is L.TEXT
    with pytest.raises(FormulaError):
        compile_formula("SOMA(SOMA([preço]))", SCHEMA, context="aggregate")


def test_division_guards_recorded() -> None:
    f = compile_formula("[preço] / [quantidade] + MOD(1; [quantidade])", SCHEMA)
    assert len(f.div_guards) == 2


@pytest.mark.parametrize(
    ("pt", "en"),
    [
        ("SE([a] > 1,5; ARRED([a]; 2); 0)", "IF([a] > 1.5, ROUND([a], 2), 0)"),
        ('CONCAT([x]; "a""b")', 'CONCATENATE([x], "a""b")'),
        ("(1 + 2) * 3 - 4 / (5 - 6)", "(1 + 2) * 3 - 4 / (5 - 6)"),
        ("ÉNULO([coluna com ]] colchete])", "ISBLANK([coluna com ]] colchete])"),
        ("VERDADEIRO", "TRUE"),
    ],
)
def test_render_roundtrip(pt: str, en: str) -> None:
    assert render(parse(pt, "pt-BR"), "en-US") == en
    assert render(parse(en, "en-US"), "pt-BR") == pt
