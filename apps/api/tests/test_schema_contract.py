"""Schema contract (CLAUDE.md §16): infer_schema() must match the schema DuckDB actually produces.

Every node type must have fixtures here. A divergence is a bug.
"""

from __future__ import annotations

from typing import Any

import pytest

from forja.compiler.analyze import analyze
from forja.engine.duck import Engine
from forja.nodes.registry import all_specs
from helpers import FakeSources, actual_schema, chain_of, pipeline, src

# (node type, list of configs applied on top of the "vendas" source)
FIXTURES: dict[str, list[dict[str, Any]]] = {
    "source": [{}],
    "select": [
        {"columns": ["uf", "valor"]},
        {"mode": "drop", "columns": ["cidade"], "renames": {"uf": "estado"}},
    ],
    "cast": [
        {
            "casts": [
                {"column": "data_txt", "to": "date", "format": "%d/%m/%Y"},
                {"column": "preço_txt", "to": "decimal", "decimal_separator": ","},
            ]
        },
        {
            "casts": [
                {"column": "quantidade", "to": "text"},
                {"column": "valor", "to": "integer"},
                {"column": "ativo", "to": "text"},
                {"column": "data_venda", "to": "datetime"},
            ]
        },
        {"casts": [{"column": "preço_txt", "to": "decimal", "decimal_separator": ",", "precision": 12, "scale": 2}]},
        {"casts": [{"column": "uf", "to": "boolean"}, {"column": "data_venda", "to": "text", "format": "dd/mm/aaaa"}]},
    ],
    "calculated": [
        {"name": "receita", "formula": "[valor] * [quantidade]"},
        {"name": "uf", "mode": "replace", "formula": "MINÚSCULA([uf])"},
        {"name": "mes", "formula": "MÊS([data_venda])"},
        {"name": "flag", "formula": "E([ativo]; [quantidade] > 1)"},
        {"name": "dt", "formula": "FIMMÊS([data_venda]; 0)"},
    ],
    "filter": [
        {"rules": {"op": "and", "conditions": [{"column": "uf", "operator": "eq", "value": "PR"}]}},
        {"mode": "formula", "formula": "[quantidade] > 1"},
    ],
    "sort": [{"keys": [{"column": "valor", "direction": "desc", "nulls": "first"}, {"column": "uf"}]}],
    "group_by": [
        {
            "keys": ["uf"],
            "aggs": [
                {"column": "valor", "fn": "sum", "as": "total"},
                {"fn": "count"},
                {"column": "quantidade", "fn": "sum", "as": "qtd"},
                {"column": "valor", "fn": "avg", "as": "media"},
                {"column": "cidade", "fn": "concat", "as": "cidades", "order_by": "cidade"},
                {"column": "data_venda", "fn": "max", "as": "ultima"},
                {"column": "cidade", "fn": "count_distinct", "as": "n_cidades"},
                {"column": "valor", "fn": "percentile", "percentile": 0.9, "as": "p90"},
                {"column": "cidade", "fn": "last", "order_by": "data_venda", "as": "ult_cidade"},
                {"column": "quantidade", "fn": "mode", "as": "moda"},
            ],
            "measures": [{"name": "ticket", "formula": "SOMA([valor]) / SOMA([quantidade])"}],
        },
        {
            "keys": [],
            "aggs": [
                {"column": "valor", "fn": "median", "as": "mediana"},
                {"column": "valor", "fn": "stddev", "as": "dp"},
            ],
        },
    ],
    "output": [{"format": "csv", "preset": "excel_br"}],
    "distinct": [{}, {"keys": ["uf"], "keep": "last", "order_by": [{"column": "data_venda"}]}],
    "sample": [{"mode": "first", "rows": 2}, {"mode": "random", "rows": 2}, {"mode": "percent", "percent": 50}],
    "text_clean": [{"columns": ["cidade"], "case": "title", "remove_accents": True, "empty_as_null": True}],
    "replace": [
        {"column": "uf", "mode": "exact", "rules": [{"find": "pr", "replace": "Paraná"}], "case_sensitive": False},
        {"column": "valor", "mode": "exact", "rules": [{"find": None, "replace": "0"}]},
        {"column": "cidade", "mode": "regex", "rules": [{"find": "[aeiou]", "replace": "*"}]},
    ],
    "fill_null": [
        {"rules": [{"column": "valor", "method": "value", "value": "0,5"}]},
        {"rules": [{"column": "valor", "method": "previous"}]},
        {
            "rules": [{"column": "quantidade", "method": "mean"}, {"column": "valor", "method": "next"}],
            "order_by": [{"column": "data_venda"}],
        },
    ],
    "date_parts": [
        {
            "column": "data_venda",
            "parts": [
                "year",
                "quarter",
                "month",
                "month_name",
                "year_month",
                "week",
                "weekday",
                "weekday_name",
                "day",
                "date",
            ],
        }
    ],
    "bin": [
        {"column": "valor", "mode": "manual", "boundaries": [5, 10]},
        {"column": "quantidade", "mode": "equal", "count": 3, "name": "faixa"},
    ],
    "split": [
        {"column": "cidade", "mode": "delimiter", "delimiter": " ", "parts": 2},
        {"column": "data_txt", "mode": "position", "positions": [3, 6], "keep_original": False},
        {"column": "preço_txt", "mode": "regex", "pattern": r"(\d+),(\d+)", "parts": 2},
    ],
    "conditional": [
        {
            "name": "faixa",
            "rules": [
                {
                    "when": {"conditions": [{"column": "valor", "operator": "gt", "value": 5}]},
                    "then": {"kind": "value", "value": "alto"},
                }
            ],
            "otherwise": {"kind": "value", "value": "baixo"},
        },
        {
            "name": "valor",
            "mode": "replace",
            "rules": [
                {
                    "when": {"conditions": [{"column": "valor", "operator": "is_null"}]},
                    "then": {"kind": "column", "column": "quantidade"},
                }
            ],
            "otherwise": {"kind": "column", "column": "valor"},
        },
    ],
    "unpivot": [
        {"columns": ["quantidade", "valor"], "name_column": "medida", "value_column": "numero"},
        {"columns": ["cidade", "valor"], "drop_nulls": True},
    ],
    "window": [
        {
            "partition_by": ["uf"],
            "order_by": [{"column": "data_venda"}],
            "items": [
                {"fn": "row_number"},
                {"fn": "rank"},
                {"fn": "dense_rank"},
                {"fn": "cumulative_count"},
                {"fn": "cumulative_sum", "column": "quantidade"},
                {"fn": "cumulative_sum", "column": "valor", "as": "acum"},
                {"fn": "previous", "column": "data_venda"},
                {"fn": "next", "column": "cidade", "offset": 2},
                {"fn": "pct_of_total", "column": "valor"},
                {"fn": "moving_avg", "column": "valor", "size": 2},
                {"fn": "partition_agg", "column": "quantidade", "agg": "sum", "as": "total_uf"},
                {"fn": "partition_agg", "column": "cidade", "agg": "count_distinct", "as": "n_cidades"},
            ],
        },
    ],
    "pivot": [
        {"rows": [{"column": "uf"}], "values": [{"column": "valor", "fn": "sum"}, {"fn": "count"}]},
        {
            "rows": [{"column": "uf"}],
            "columns": {"column": "ativo"},
            "column_values": ["true", "false", None],
            "values": [{"column": "valor", "fn": "sum"}, {"column": "quantidade", "fn": "avg", "show_as": "pct_row"}],
        },
        {
            "rows": [{"column": "data_venda", "date_group": "month"}],
            "columns": {"column": "uf"},
            "column_values": ["PR", "SC", "SP"],
            "values": [{"column": "valor", "fn": "sum", "show_as": "pct_column"}],
            "totals": True,
            "filters": [{"column": "quantidade", "operator": "gt", "value": 0}],
        },
    ],
}
ANNOTATIONS = {"note", "frame"}


# Covered by test_contract_multi_input_nodes / test_sql.py / test_subflow.py.
MULTI_INPUT = {"join", "union", "lookup", "sql", "subflow"}


def test_every_node_type_has_contract_fixtures() -> None:
    missing = {s.type for s in all_specs() if not s.internal} - set(FIXTURES) - ANNOTATIONS - MULTI_INPUT
    assert not missing, f"node types without schema contract fixtures: {sorted(missing)}"


CASES = [(t, i, cfg) for t, cfgs in FIXTURES.items() for i, cfg in enumerate(cfgs)]


@pytest.mark.parametrize(("node_type", "idx", "cfg"), CASES, ids=[f"{t}-{i}" for t, i, _ in CASES])
def test_schema_contract(engine: Engine, sources: FakeSources, node_type: str, idx: int, cfg: dict[str, Any]) -> None:
    p = chain_of(src()) if node_type == "source" else chain_of(src(), {"type": node_type, "config": cfg})
    a = analyze(p, sources)
    last = p.nodes[-1].id
    r = a.results[last]
    assert r.ok, [i.message for i in r.issues]
    assert r.schema is not None
    assert actual_schema(engine, a, last) == r.schema


def test_contract_multi_input_pipeline(engine: Engine, sources: FakeSources) -> None:
    """Branching: one output feeding two nodes."""
    p = pipeline(
        [
            {"id": "a", **src()},
            {"id": "b", "type": "select", "config": {"columns": ["uf"]}},
            {"id": "c", "type": "calculated", "config": {"name": "x", "formula": "[valor] * 2"}},
        ],
        [("a", "b"), ("a", "c")],
    )
    a = analyze(p, sources)
    for nid in ("b", "c"):
        assert actual_schema(engine, a, nid) == a.results[nid].schema


MULTI_CASES: list[tuple[str, dict[str, Any], list[str]]] = [
    ("join", {"how": "left", "keys": [{"left": "uf", "right": "uf"}]}, ["left", "right"]),
    ("join", {"how": "inner", "keys": [{"left": "uf", "right": "uf"}]}, ["left", "right"]),
    ("join", {"how": "full", "keys": [{"left": "uf", "right": "uf"}]}, ["left", "right"]),
    ("join", {"how": "right", "keys": [{"left": "uf", "right": "uf"}]}, ["left", "right"]),
    ("join", {"how": "anti", "keys": [{"left": "uf", "right": "uf"}]}, ["left", "right"]),
    ("join", {"how": "semi", "keys": [{"left": "uf", "right": "uf"}]}, ["left", "right"]),
    ("lookup", {"keys": [{"main": "uf", "lookup": "uf"}], "columns": ["estado"]}, ["main", "lookup"]),
    ("union", {"mode": "by_name", "source_column": "origem"}, ["in_0", "in_1"]),
    ("union", {"mode": "by_position"}, ["in_0", "in_1"]),
]


@pytest.mark.parametrize(
    ("node_type", "cfg", "handles"), MULTI_CASES, ids=[f"{c[0]}-{i}" for i, c in enumerate(MULTI_CASES)]
)
def test_contract_multi_input_nodes(
    engine: Engine, sources: FakeSources, node_type: str, cfg: dict[str, Any], handles: list[str]
) -> None:
    p = pipeline(
        [{"id": "v", **src("vendas")}, {"id": "c", **src("clientes")}, {"id": "x", "type": node_type, "config": cfg}],
        [("v", "x", handles[0]), ("c", "x", handles[1])],
    )
    a = analyze(p, sources)
    r = a.results["x"]
    assert r.ok, [i.message for i in r.issues]
    assert actual_schema(engine, a, "x") == r.schema
