"""Sub-flows: a template embedded as one node (CLAUDE.md §19, Fase 3)."""

from __future__ import annotations

from typing import Any

from forja.compiler.analyze import analyze
from forja.compiler.build import compile_chain, to_sql
from forja.engine import service
from forja.engine.describe import make_describer
from forja.engine.duck import Engine
from helpers import FakeSources, actual_schema, pipeline, run, src

# Inner nodes reuse the ids "n0"/"n1" on purpose: the outer pipeline uses them too.
CLEAN: dict[str, Any] = {
    "locale": "pt-BR",
    "nodes": [
        {"id": "n0", "type": "cast", "config": {"casts": [{"column": "data_txt", "to": "date", "format": "%d/%m/%Y"}]}},
        {"id": "n1", "type": "calculated", "config": {"name": "total", "formula": "[quantidade] * 1,5"}},
        {"id": "n2", "type": "filter", "config": {"mode": "formula", "formula": '[uf] <> "SP"'}},
    ],
    "edges": [{"id": "a", "source": "n0", "target": "n1"}, {"id": "b", "source": "n1", "target": "n2"}],
    "inputs": [{"name": "Vendas", "targets": [{"node": "n0", "handle": "in"}]}],
    "output": "n2",
}


def sub(flow: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"type": "subflow", "config": {"template_name": "Limpeza", "flow": flow, **extra}}


def test_subflow_matches_the_same_nodes_inline(engine: Engine, sources: FakeSources) -> None:
    p = pipeline([{"id": "n0", **src()}, {"id": "n1", **sub(CLEAN)}], [("n0", "n1", "in_0")])
    a = analyze(p, sources)
    r = a.results["n1"]
    assert r.ok, [i.message for i in r.issues]
    assert r.schema is not None
    assert actual_schema(engine, a, "n1") == r.schema
    assert "total" in r.changed_columns

    inline = pipeline(
        [{"id": "s", **src()}, *CLEAN["nodes"]],
        [("s", "n0"), ("n0", "n1"), ("n1", "n2")],
    )
    b = analyze(inline, sources)
    assert b.results["n2"].schema == r.schema
    assert sorted(run(engine, a, "n1")) == sorted(run(engine, b, "n2"))
    assert len(run(engine, a, "n1")) == 3


def test_subflow_with_two_inputs(engine: Engine, sources: FakeSources) -> None:
    flow = {
        "nodes": [
            {"id": "j", "type": "join", "config": {"how": "left", "keys": [{"left": "uf", "right": "uf"}]}},
            {"id": "s", "type": "select", "config": {"columns": ["uf", "cidade", "estado"]}},
        ],
        "edges": [{"id": "e", "source": "j", "target": "s"}],
        "inputs": [
            {"name": "Vendas", "targets": [{"node": "j", "handle": "left"}]},
            {"name": "Clientes", "targets": [{"node": "j", "handle": "right"}]},
        ],
        "output": "s",
    }
    p = pipeline(
        [{"id": "v", **src("vendas")}, {"id": "c", **src("clientes")}, {"id": "x", **sub(flow)}],
        [("v", "x", "in_0"), ("c", "x", "in_1")],
    )
    a = analyze(p, sources)
    assert a.results["x"].ok, [i.message for i in a.results["x"].issues]
    assert actual_schema(engine, a, "x") == a.results["x"].schema
    assert ("PR", "Curitiba", "Paraná") in run(engine, a, "x")


def test_missing_input_and_inner_errors_point_to_the_inner_node(sources: FakeSources) -> None:
    p = pipeline([{"id": "s", **src("clientes")}, {"id": "x", **sub(CLEAN)}], [])
    r = analyze(p, sources).results["x"]
    assert [i.code for i in r.issues] == ["MISSING_INPUT"]
    assert "entrada 1" in r.issues[0].message

    # "clientes" has no data_txt: the inner cast fails, reported on the sub-flow node.
    p = pipeline([{"id": "s", **src("clientes")}, {"id": "x", **sub(CLEAN)}], [("s", "x", "in_0")])
    r = analyze(p, sources).results["x"]
    assert r.status == "error"
    assert r.issues[0].code == "COLUMN_NOT_FOUND"
    assert r.issues[0].node_id == "x"
    assert r.issues[0].message.startswith('Em "Alterar tipo": ')


def test_structure_errors(sources: FakeSources) -> None:
    flow = {**CLEAN, "nodes": [*CLEAN["nodes"], {"id": "f", "type": "source", "config": {"source_id": "vendas"}}]}
    p = pipeline([{"id": "s", **src()}, {"id": "x", **sub(flow)}], [("s", "x", "in_0")])
    r = analyze(p, sources).results["x"]
    assert [i.code for i in r.issues] == ["SUBFLOW_INVALID"]
    assert "Fonte" in r.issues[0].message

    p = pipeline([{"id": "s", **src()}, {"id": "x", **sub({**CLEAN, "output": None})}], [("s", "x", "in_0")])
    assert "saída única" in analyze(p, sources).results["x"].issues[0].message


def test_inner_runtime_warnings_reach_stats(engine: Engine, sources: FakeSources) -> None:
    p = pipeline([{"id": "n0", **src()}, {"id": "n1", **sub(CLEAN)}], [("n0", "n1", "in_0")])
    a = analyze(p, sources)
    st = service.stats(engine, a, "n1", timeout=None)
    assert st.row_count == 3
    assert st.input_row_counts == {"in_0": 4}
    assert [i.code for i in st.issues] == ["CAST_FAILURES"]
    assert st.issues[0].message.startswith('Em "Alterar tipo": ')


def test_nested_subflow_and_sql_inside(engine: Engine, sources: FakeSources) -> None:
    sql_flow = {
        "nodes": [{"id": "q", "type": "sql", "config": {"query": "SELECT uf, SUM(total) AS t FROM input GROUP BY uf"}}],
        "edges": [],
        "inputs": [{"name": "Tabela", "targets": [{"node": "q", "handle": "in_0"}]}],
        "output": "q",
    }
    outer_flow = {
        "nodes": [{"id": "inner", **sub(CLEAN)}, {"id": "agg", **sub(sql_flow)}],
        "edges": [{"id": "e", "source": "inner", "target": "agg", "target_handle": "in_0"}],
        "inputs": [{"name": "Vendas", "targets": [{"node": "inner", "handle": "in_0"}]}],
        "output": "agg",
    }
    p = pipeline([{"id": "s", **src()}, {"id": "x", **sub(outer_flow)}], [("s", "x", "in_0")])
    a = analyze(p, sources, make_describer(engine))
    r = a.results["x"]
    assert r.ok, [i.message for i in r.issues]
    assert [c.name for c in r.schema or []] == ["uf", "t"]
    assert sorted(run(engine, a, "x")) == [("PR", 7.5), ("SC", 0.0)]
    # "Copiar como SQL" shows the inner steps as nested CTEs.
    assert '"x/inner/n1"' in to_sql(compile_chain(a, "x", for_display=True).query())
