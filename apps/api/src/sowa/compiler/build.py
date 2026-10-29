"""Compile the upstream subgraph of a node into one query with a CTE per node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlglot import exp

from sowa.compiler.analyze import Analysis
from sowa.compiler.graph import upstream_of
from sowa.compiler.hashing import node_hashes
from sowa.domain.issues import Issue, IssueCode
from sowa.domain.schema import Schema
from sowa.nodes.base import ident


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
    # Nodes read from the materialized cache.
    cached: frozenset[str] = frozenset()

    def wrap(self, query: exp.Select) -> exp.Select:
        """Attach all CTEs to `query` (which refers to them by node id).

        The chain CTEs go first, so CTEs already declared on `query` can use them.
        """
        q = query.copy()
        own = q.args.get("with_")
        # Built as AST nodes: the `with_()` builder re-parses names (and "a/b" isn't parseable).
        ctes = [exp.CTE(this=sel.copy(), alias=exp.TableAlias(this=ident(name))) for name, sel in self.ctes]
        if own is not None:
            ctes += own.expressions
        q.set("with_", exp.With(expressions=ctes) if ctes else None)
        return q

    def query(self) -> exp.Select:
        return self.wrap(cte_ref(self.target))


class CacheLookup(Protocol):
    """Materialized results of nodes, keyed by node hash (see engine.matcache)."""

    def lookup(self, key: str) -> str | None: ...


def compile_chain(
    analysis: Analysis,
    node_id: str,
    *,
    for_display: bool = False,
    cache: CacheLookup | None = None,
    keep_inputs: bool = False,
) -> Chain:
    """Query chain up to ``node_id``. ``keep_inputs`` keeps the CTEs of the node's direct inputs
    even when the node itself comes from the cache (``runtime_issues`` queries them)."""
    r = analysis.results.get(node_id)
    if r is None:
        raise CompileError([Issue(node_id=node_id, code=IssueCode.NODE_NOT_FOUND, message="Nó não encontrado.")])
    ids = upstream_of(analysis.graph, node_id)
    for nid in ids:
        res = analysis.results[nid]
        if not res.ok or res.spec is None or res.config is None:
            issues = [i for i in res.issues if i.severity != "warning"] or [
                Issue(node_id=nid, code=IssueCode.UPSTREAM_ERROR, message="Nó com erro.")
            ]
            raise CompileError(issues)

    # Cacheable nodes with a materialized result are read from Parquet; their upstream is skipped.
    cached: dict[str, str] = {}
    if cache is not None and not for_display:
        hashes = node_hashes(analysis, node_id)
        for nid in ids:
            spec = analysis.results[nid].spec
            if spec is not None and spec.cacheable and (path := cache.lookup(hashes[nid])):
                cached[nid] = path
    needed: set[str] = set()
    stack = [node_id]
    while stack:
        n = stack.pop()
        if n in needed:
            continue
        needed.add(n)
        if n not in cached or (keep_inputs and n == node_id):
            stack.extend(analysis.results[n].inputs.values())

    ctes: list[tuple[str, exp.Select]] = []
    for nid in ids:
        res = analysis.results[nid]
        assert res.spec is not None
        assert res.config is not None
        if nid not in needed or res.spec.annotation:
            continue
        if nid in cached:
            src = exp.Table(this=exp.Anonymous(this="read_parquet", expressions=[exp.Literal.string(cached[nid])]))
            ctes.append((nid, exp.select(exp.Star()).from_(src)))
            continue
        inputs = {h: cte_ref(u) for h, u in res.inputs.items()}
        schemas: dict[str, Schema] = {
            h: s for h, u in res.inputs.items() if (s := analysis.results[u].schema) is not None
        }
        ctx = analysis.context(nid, for_display=for_display)
        ctes.append((nid, res.spec.compile(res.config, inputs, schemas, ctx)))
    return Chain(node_id, ctes, cached=frozenset(cached))


def to_sql(query: exp.Expr, pretty: bool = False) -> str:
    return query.sql(dialect="duckdb", pretty=pretty, identify=True)
