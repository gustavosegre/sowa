"""SQL node: SELECT-only over the inputs, schema via DESCRIBE, never touching files."""

from __future__ import annotations

import pytest

from helpers import FakeSources, actual_schema, pipeline, run, src
from sowa.compiler.analyze import analyze
from sowa.domain.issues import IssueCode
from sowa.engine.describe import make_describer
from sowa.engine.duck import Engine
from sowa.nodes.sql import SqlRejected, parse_select


def sql_pipeline(query: str, two_inputs: bool = False):  # type: ignore[no-untyped-def]
    nodes = [{"id": "v", **src("vendas")}, {"id": "q", "type": "sql", "config": {"query": query}}]
    edges: list[tuple[str, str] | tuple[str, str, str]] = [("v", "q", "in_0")]
    if two_inputs:
        nodes.append({"id": "c", **src("clientes")})
        edges.append(("c", "q", "in_1"))
    return pipeline(nodes, edges)


@pytest.mark.parametrize(
    ("query", "fragment"),
    [
        ("DELETE FROM input", "SELECT"),
        ("SELECT 1; SELECT 2", "única"),
        ("SELECT * FROM read_csv('C:/x.csv')", "Funções de tabela"),
        ("SELECT * FROM read_parquet('x.parquet')", "Funções de tabela"),
        ("SELECT getenv('PATH')", "GETENV"),
        ("SELECT * FROM outra_tabela", "outra_tabela"),
        ("SELECT * FROM main.input", "entrada"),
        ("SELECT * FROM glob('*')", "Funções de tabela"),
        ("SELEC * FROM input", "sintaxe"),
        ("", "SELECT"),
    ],
)
def test_rejected(query: str, fragment: str) -> None:
    with pytest.raises(SqlRejected) as e:
        parse_select(query, {"input"})
    assert fragment in str(e.value)


def test_allowed_with_ctes() -> None:
    parse_select("WITH t AS (SELECT * FROM input) SELECT uf FROM t WHERE uf <> 'SP'", {"input"})


def test_sql_node_schema_and_result(engine: Engine, sources: FakeSources) -> None:
    p = sql_pipeline(
        "SELECT v.uf, c.estado, SUM(v.valor) AS total FROM input v LEFT JOIN input_1 c ON v.uf = c.uf "
        "GROUP BY ALL ORDER BY v.uf",
        two_inputs=True,
    )
    a = analyze(p, sources, make_describer(engine))
    r = a.results["q"]
    assert r.ok, [i.message for i in r.issues]
    assert [(c.name, c.type.value) for c in r.schema or []] == [
        ("uf", "text"),
        ("estado", "text"),
        ("total", "decimal"),
    ]
    assert actual_schema(engine, a, "q") == r.schema
    assert run(engine, a, "q") == [("PR", "Paraná", 10.5), ("SC", "Santa Catarina", 2.0), ("SP", None, 7.25)]


def test_binder_errors_become_node_issues(engine: Engine, sources: FakeSources) -> None:
    a = analyze(sql_pipeline("SELECT coluna_que_nao_existe FROM input"), sources, make_describer(engine))
    issue = a.results["q"].issues[0]
    assert issue.code is IssueCode.SQL_NOT_ALLOWED
    assert issue.detail
    assert "coluna_que_nao_existe" in issue.detail


def test_forbidden_sql_is_a_node_error(engine: Engine, sources: FakeSources) -> None:
    a = analyze(sql_pipeline("SELECT * FROM read_parquet('../../segredo.parquet')"), sources, make_describer(engine))
    assert a.results["q"].status == "error"
    assert a.results["q"].issues[0].code is IssueCode.SQL_NOT_ALLOWED
