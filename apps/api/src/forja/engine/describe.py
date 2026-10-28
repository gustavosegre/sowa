"""Schema of an arbitrary query over upstream nodes, via DuckDB's DESCRIBE (binds, reads no data)."""

from __future__ import annotations

import hashlib

from sqlglot import exp

from forja.compiler.analyze import Analysis, Describer, analyze
from forja.compiler.build import Chain, compile_chain
from forja.domain.pipeline import Pipeline
from forja.domain.schema import Column, Schema
from forja.domain.types import from_duckdb
from forja.engine.cache import LRU
from forja.engine.duck import Engine
from forja.engine.matcache import get_cache
from forja.nodes.base import SourceResolver

_memo: LRU[Schema] = LRU(max_items=500)


def make_describer(engine: Engine, timeout: float = 10.0) -> Describer:
    def describe(analysis: Analysis, upstream: list[str], query: exp.Select) -> Schema:
        ctes: list[tuple[str, exp.Select]] = []
        seen: set[str] = set()
        for up in upstream:
            for name, sel in compile_chain(analysis, up, cache=get_cache()).ctes:
                if name not in seen:
                    seen.add(name)
                    ctes.append((name, sel))
        sql = Chain(target="", ctes=ctes).wrap(query).sql(dialect="duckdb", identify=True)
        key = hashlib.sha256(sql.encode()).hexdigest()
        found = _memo.get(key)
        if found is not None:
            return found
        rows = engine.rows(f"DESCRIBE {sql}", timeout)
        schema = Schema(columns=[Column(name=str(r[0]), type=from_duckdb(str(r[1]))) for r in rows])
        _memo.put(key, schema)
        return schema

    return describe


def analyze_live(pipeline: Pipeline, sources: SourceResolver) -> Analysis:
    """Static analysis with the engine available (needed by nodes whose schema comes from SQL)."""
    from forja.engine.duck import get_engine

    return analyze(pipeline, sources, make_describer(get_engine()))
