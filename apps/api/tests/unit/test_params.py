"""Global parameters ({data_corte}) in formulas and visual filters."""

from __future__ import annotations

import datetime as dt

import pytest

from forja.compiler.analyze import analyze
from forja.domain.issues import IssueCode
from forja.domain.pipeline import Parameter
from forja.domain.schema import Schema
from forja.domain.types import LogicalType as L
from forja.engine.duck import Engine
from forja.formula.parser import parse
from forja.formula.render import render
from forja.formula.service import compile_formula
from forja.formula.typecheck import FormulaError
from helpers import FakeSources, chain_of, run, src

PARAMS = [
    Parameter(name="data_corte", type=L.DATE, value="15/03/2025"),
    Parameter(name="meta", type=L.DECIMAL, value="5,5"),
]


def test_param_in_formula_is_typed_literal() -> None:
    f = compile_formula("[d] >= {data_corte}", Schema.of(("d", L.DATE)), params=PARAMS)
    assert f.type is L.BOOLEAN
    assert "CAST('2025-03-15' AS DATE)" in f.sql.sql("duckdb")


def test_unknown_param_is_a_positioned_error() -> None:
    with pytest.raises(FormulaError) as e:
        compile_formula("[x] * {taxa}", Schema.of(("x", L.DECIMAL)), params=PARAMS)
    assert e.value.code is IssueCode.PARAM_NOT_FOUND
    assert (e.value.start, e.value.end) == (6, 12)
    assert "{data_corte}" in e.value.message


def test_render_keeps_params() -> None:
    assert render(parse("SE([v] > {meta}; 1; 0)", "pt-BR"), "en-US") == "IF([v] > {meta}, 1, 0)"


def test_params_in_pipeline(engine: Engine, sources: FakeSources) -> None:
    p = chain_of(
        src(),
        {
            "type": "filter",
            "config": {"rules": {"conditions": [{"column": "data_venda", "operator": "gte", "value": "{data_corte}"}]}},
        },
        {"type": "calculated", "config": {"name": "acima", "formula": "[valor] > {meta}"}},
        {"type": "select", "config": {"mode": "keep", "columns": ["cidade", "data_venda", "acima"]}},
        {"type": "sort", "config": {"keys": [{"column": "data_venda"}]}},
    )
    p.settings.params = PARAMS
    a = analyze(p, sources)
    assert a.results["n4"].ok, [i.message for i in a.results["n4"].issues]
    assert run(engine, a, "n4") == [
        ("Londrina", dt.date(2025, 3, 15), None),
        ("São Paulo", dt.date(2025, 3, 20), True),
        ("Curitiba", dt.date(2025, 12, 31), True),
    ]


def test_missing_param_in_filter_value(sources: FakeSources) -> None:
    p = chain_of(
        src(),
        {
            "type": "filter",
            "config": {"rules": {"conditions": [{"column": "uf", "operator": "eq", "value": "{estado}"}]}},
        },
    )
    issue = analyze(p, sources).results["n1"].issues[0]
    assert issue.code is IssueCode.PARAM_NOT_FOUND
