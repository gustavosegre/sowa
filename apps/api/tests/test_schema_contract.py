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
}
ANNOTATIONS = {"note", "frame"}


def test_every_node_type_has_contract_fixtures() -> None:
    missing = {s.type for s in all_specs()} - set(FIXTURES) - ANNOTATIONS
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
