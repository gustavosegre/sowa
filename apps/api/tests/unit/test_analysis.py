"""Graph analysis: cycles, missing inputs, blocked downstream, visible breakage on rename."""

from __future__ import annotations

from forja.compiler.analyze import analyze
from forja.compiler.graph import build_graph, upstream_of
from forja.domain.issues import IssueCode
from helpers import FakeSources, chain_of, pipeline, src


def test_topological_order_and_upstream() -> None:
    p = pipeline(
        [{"id": i, "type": "note"} for i in "abcd"],
        [("a", "b"), ("b", "c"), ("a", "d")],
    )
    g = build_graph(p)
    assert g.order.index("a") < g.order.index("b") < g.order.index("c")
    assert upstream_of(g, "c") == ["a", "b", "c"]
    assert upstream_of(g, "d") == ["a", "d"]


def test_cycle_is_an_error(sources: FakeSources) -> None:
    p = pipeline(
        [
            {"id": "s", **src()},
            {"id": "x", "type": "sort", "config": {"keys": [{"column": "uf"}]}},
            {"id": "y", "type": "sort", "config": {"keys": [{"column": "uf"}]}},
        ],
        [("s", "x"), ("x", "y"), ("y", "x")],
    )
    a = analyze(p, sources)
    assert a.results["s"].status == "ok"
    for nid in ("x", "y"):
        assert a.results[nid].status == "error"
        assert a.results[nid].issues[0].code is IssueCode.CYCLE


def test_missing_input_and_unknown_type(sources: FakeSources) -> None:
    p = pipeline([{"id": "f", "type": "filter"}, {"id": "z", "type": "nao_existe"}], [])
    a = analyze(p, sources)
    assert a.results["f"].issues[0].code is IssueCode.MISSING_INPUT
    assert a.results["z"].issues[0].code is IssueCode.UNKNOWN_NODE_TYPE


def test_invalid_config_is_a_node_issue_not_a_request_error(sources: FakeSources) -> None:
    p = chain_of(src(), {"type": "sort", "config": {"keys": [{"column": "uf", "direction": "sideways"}]}})
    r = analyze(p, sources).results["n1"]
    assert r.status == "error"
    assert r.issues[0].code is IssueCode.INVALID_CONFIG
    assert "keys.0.direction" in r.issues[0].message


def test_rename_upstream_breaks_downstream_visibly(sources: FakeSources) -> None:
    p = chain_of(
        src(),
        {
            "type": "select",
            "config": {"mode": "drop", "columns": [], "renames": {"valor": "preço"}},
            "ui": {"label": "Selecionar colunas"},
        },
        {"type": "calculated", "config": {"name": "dobro", "formula": "[valor] * 2"}},
        {"type": "sort", "config": {"keys": [{"column": "dobro"}]}},
    )
    a = analyze(p, sources)
    assert a.results["n1"].status == "ok"
    err = a.results["n2"]
    assert err.status == "error"
    assert err.issues[0].code is IssueCode.COLUMN_NOT_FOUND
    assert err.issues[0].position is not None
    blocked = a.results["n3"]
    assert blocked.status == "blocked"
    assert "Bloqueado" in blocked.issues[0].message


def test_column_not_found_names_the_upstream_node(sources: FakeSources) -> None:
    p = chain_of(src(), {"type": "sort", "config": {"keys": [{"column": "inexistente"}]}})
    p.nodes[0].ui.label = "Vendas 2025"
    issue = analyze(p, sources).results["n1"].issues[0]
    assert issue.code is IssueCode.COLUMN_NOT_FOUND
    assert issue.column == "inexistente"
    assert '"Vendas 2025"' in issue.message
    assert issue.node_id == "n1"


def test_changed_columns_pills(sources: FakeSources) -> None:
    p = chain_of(
        src(),
        {"type": "cast", "config": {"casts": [{"column": "quantidade", "to": "decimal"}]}},
        {"type": "calculated", "config": {"name": "novo", "formula": "1"}},
    )
    a = analyze(p, sources)
    assert a.results["n1"].changed_columns == ["quantidade"]
    assert a.results["n2"].changed_columns == ["novo"]


def test_source_errors() -> None:
    a = analyze(chain_of({"type": "source", "config": {"source_id": "nope"}}), FakeSources())
    assert a.results["n0"].issues[0].code is IssueCode.SOURCE_NOT_FOUND
    a = analyze(chain_of({"type": "source", "config": {}}), FakeSources())
    assert a.results["n0"].issues[0].code is IssueCode.SOURCE_NOT_FOUND


def test_filter_value_type_errors(sources: FakeSources) -> None:
    p = chain_of(
        src(),
        {
            "type": "filter",
            "config": {
                "rules": {
                    "conditions": [
                        {"column": "valor", "operator": "gt", "value": "abc"},
                        {"column": "uf", "operator": "is_true"},
                    ]
                }
            },
        },
    )
    issues = analyze(p, sources).results["n1"].issues
    assert [i.code for i in issues] == [IssueCode.TYPE_MISMATCH, IssueCode.TYPE_MISMATCH]
    assert "abc" in issues[0].message


def test_duplicate_names_in_group_by(sources: FakeSources) -> None:
    p = chain_of(
        src(), {"type": "group_by", "config": {"keys": ["uf"], "aggs": [{"column": "valor", "fn": "sum", "as": "uf"}]}}
    )
    assert analyze(p, sources).results["n1"].issues[0].code is IssueCode.DUPLICATE_COLUMN


def test_group_by_numeric_agg_on_text(sources: FakeSources) -> None:
    p = chain_of(src(), {"type": "group_by", "config": {"keys": ["uf"], "aggs": [{"column": "cidade", "fn": "sum"}]}})
    issue = analyze(p, sources).results["n1"].issues[0]
    assert issue.code is IssueCode.TYPE_MISMATCH
    assert "Alterar tipo" in (issue.hint or "")
