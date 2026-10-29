"""Pivot "Mostrar valores como": Diferença de / Soma acumulada em (CLAUDE.md §10).

Source "vendas" (conftest): PR → quantidade 3 + 2, valor 10.5 + NULL (ativo true);
SC → 0, 2.0 (false); SP → 1, 7.25 (false).
"""

from __future__ import annotations

from typing import Any

import pytest

from forja.compiler.analyze import analyze
from forja.engine.duck import Engine
from helpers import FakeSources, chain_of, run, src


def pivot(engine: Engine, sources: FakeSources, cfg: dict[str, Any]) -> list[tuple[Any, ...]]:
    p = chain_of(src(), {"type": "pivot", "config": cfg})
    a = analyze(p, sources)
    r = a.results[p.nodes[-1].id]
    assert r.ok, [i.message for i in r.issues]
    return run(engine, a, p.nodes[-1].id)


def issues(sources: FakeSources, cfg: dict[str, Any]) -> list[str]:
    p = chain_of(src(), {"type": "pivot", "config": cfg})
    return [i.message for i in analyze(p, sources).results[p.nodes[-1].id].issues]


def test_along_a_rows_field(engine: Engine, sources: FakeSources) -> None:
    rows = pivot(
        engine,
        sources,
        {
            "rows": [{"column": "uf"}],
            "values": [
                {"column": "quantidade", "fn": "sum", "show_as": "running_total", "base_field": "uf"},
                {"column": "valor", "fn": "sum", "show_as": "difference", "base_field": "uf"},
                {
                    "column": "quantidade",
                    "fn": "sum",
                    "show_as": "difference",
                    "base_field": "uf",
                    "base_item": "fixed",
                    "base_value": "SC",
                    "label": "vs SC",
                },
            ],
        },
    )
    assert rows == [("PR", 5, None, 5), ("SC", 5, -8.5, 0), ("SP", 6, 5.25, 1)]


def test_running_total_restarts_in_each_group(engine: Engine, sources: FakeSources) -> None:
    rows = pivot(
        engine,
        sources,
        {
            "rows": [{"column": "ativo"}, {"column": "uf"}],
            "values": [{"column": "quantidade", "fn": "sum", "show_as": "running_total", "base_field": "uf"}],
        },
    )
    assert rows == [(False, "SC", 0), (False, "SP", 1), (True, "PR", 5)]


def test_across_the_columns_field(engine: Engine, sources: FakeSources) -> None:
    base: dict[str, Any] = {"columns": {"column": "uf"}, "column_values": ["PR", "SC", "SP"]}
    measure = {"column": "quantidade", "fn": "sum", "base_field": "uf"}
    assert pivot(engine, sources, {**base, "values": [{**measure, "show_as": "difference"}]}) == [(None, -5, 1)]
    fixed = {**measure, "show_as": "difference", "base_item": "fixed", "base_value": "PR"}
    assert pivot(engine, sources, {**base, "values": [fixed]}) == [(0, -5, -4)]
    assert pivot(engine, sources, {**base, "values": [{**measure, "show_as": "running_total"}]}) == [(5, 5, 6)]


@pytest.mark.parametrize(
    ("value", "extra", "message"),
    [
        ({"show_as": "difference"}, {}, 'Escolha o campo base de "Diferença de"'),
        ({"show_as": "running_total", "base_field": "cidade"}, {}, 'O campo base "cidade"'),
        ({"show_as": "difference", "base_field": "uf", "base_item": "fixed"}, {}, "Escolha o item fixo"),
        ({"show_as": "running_total", "base_field": "uf"}, {"totals": True}, "não funciona com totais"),
        ({"show_as": "difference", "base_field": "uf", "fn": "min", "column": "cidade"}, {}, "medida numérica"),
    ],
)
def test_configuration_errors(sources: FakeSources, value: dict[str, Any], extra: dict[str, Any], message: str) -> None:
    cfg = {"rows": [{"column": "uf"}], "values": [{"column": "quantidade", "fn": "sum", **value}], **extra}
    assert any(message in m for m in issues(sources, cfg)), issues(sources, cfg)


def test_fixed_item_must_be_a_column_value(sources: FakeSources) -> None:
    cfg = {
        "columns": {"column": "uf"},
        "column_values": ["PR", "SC"],
        "values": [
            {
                "column": "quantidade",
                "fn": "sum",
                "show_as": "difference",
                "base_field": "uf",
                "base_item": "fixed",
                "base_value": "RS",
            }
        ],
    }
    assert any('O item "RS"' in m for m in issues(sources, cfg))
