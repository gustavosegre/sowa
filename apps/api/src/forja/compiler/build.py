"""Compile the upstream subgraph of a node into one query with a CTE per node."""

from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp

from forja.compiler.analyze import Analysis
from forja.compiler.graph import upstream_of
from forja.domain.issues import Issue, IssueCode
from forja.domain.schema import Schema
from forja.nodes.base import ident


class CompileError(Exception):
    def __init__(self, issues: list[Issue]) -> None:
        super().__init__("; ".join(i.message for i in issues))
        self.issues = issues


def cte_ref(node_id: str) -> exp.Select:
    return exp.select(exp.Star()).from_(exp.Table(this=ident(node_id)))


@dataclass
class Chain:
    """A compiled chain of CTEs ending at `target`."""

    target: str
    ctes: list[tuple[str, exp.Select]]

    def wrap(self, query: exp.Select) -> exp.Select:
        """Attach all CTEs to `query` (which refers to them by node id).

        The chain CTEs go first, so CTEs already declared on `query` can use them.
        """
        q = query.copy()
        own = q.args.get("with_")
        q.set("with_", None)
        for name, sel in self.ctes:
            q = q.with_(ident(name), as_=sel.copy(), append=True)
        if own is not None:
            for cte in own.expressions:
                q = q.with_(cte.args["alias"].this, as_=cte.this, append=True)
        return q

    def query(self) -> exp.Select:
        return self.wrap(cte_ref(self.target))


def compile_chain(analysis: Analysis, node_id: str, *, for_display: bool = False) -> Chain:
    r = analysis.results.get(node_id)
    if r is None:
        raise CompileError([Issue(node_id=node_id, code=IssueCode.NODE_NOT_FOUND, message="Nó não encontrado.")])
    ids = upstream_of(analysis.graph, node_id)
    ctes: list[tuple[str, exp.Select]] = []
    for nid in ids:
        res = analysis.results[nid]
        if not res.ok or res.spec is None or res.config is None:
            issues = [i for i in res.issues if i.severity != "warning"] or [
                Issue(node_id=nid, code=IssueCode.UPSTREAM_ERROR, message="Nó com erro.")
            ]
            raise CompileError(issues)
        if res.spec.annotation:
            continue
        inputs = {h: cte_ref(u) for h, u in res.inputs.items()}
        schemas: dict[str, Schema] = {
            h: s for h, u in res.inputs.items() if (s := analysis.results[u].schema) is not None
        }
        ctx = analysis.context(nid, for_display=for_display)
        ctes.append((nid, res.spec.compile(res.config, inputs, schemas, ctx)))
    return Chain(node_id, ctes)


def to_sql(query: exp.Expr, pretty: bool = False) -> str:
    return query.sql(dialect="duckdb", pretty=pretty, identify=True)
