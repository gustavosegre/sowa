"""Materialized cache of cacheable nodes (CLAUDE.md §13)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from forja.compiler.analyze import analyze
from forja.compiler.build import compile_chain, to_sql
from forja.compiler.hashing import node_hashes
from forja.engine import service
from forja.engine.duck import Engine
from forja.engine.matcache import MaterializedCache, get_cache
from helpers import FakeSources, chain_of, src

GROUP = {"type": "group_by", "config": {"keys": ["uf"], "aggs": [{"column": "valor", "fn": "sum", "as": "total"}]}}
SORT = {"type": "sort", "config": {"keys": [{"column": "uf"}]}}


def test_counting_a_cacheable_node_materializes_it(engine: Engine, sources: FakeSources) -> None:
    get_cache().clear()
    p = chain_of(src(), GROUP, SORT)
    a = analyze(p, sources)
    before = engine.rows(compile_chain(a, "n2").query())
    assert compile_chain(a, "n2", cache=get_cache()).cached == frozenset()

    service.count_cache.clear()
    assert service.count_rows(engine, a, "n1", timeout=None) == 3

    chain = compile_chain(a, "n2", cache=get_cache())
    assert chain.cached == {"n1"}
    sql = to_sql(chain.query())
    assert "READ_PARQUET" in sql
    assert "vendas.parquet" not in sql  # the source isn't read anymore
    assert engine.rows(chain.query()) == before


def test_editing_a_node_invalidates_it_and_downstream_only(engine: Engine, sources: FakeSources) -> None:
    get_cache().clear()
    p = chain_of(src(), GROUP, SORT)
    a = analyze(p, sources)
    service.count_cache.clear()
    service.count_rows(engine, a, "n1", timeout=None)
    old = node_hashes(a, "n2")

    p.nodes[1].config["aggs"][0]["fn"] = "max"
    a2 = analyze(p, sources)
    new = node_hashes(a2, "n2")
    assert new["n0"] == old["n0"]
    assert new["n1"] != old["n1"]
    assert new["n2"] != old["n2"]
    assert compile_chain(a2, "n2", cache=get_cache()).cached == frozenset()


def test_copy_as_sql_never_uses_the_cache(engine: Engine, sources: FakeSources) -> None:
    p = chain_of(src(), GROUP)
    a = analyze(p, sources)
    service.count_cache.clear()
    service.count_rows(engine, a, "n1", timeout=None)
    assert "READ_PARQUET('Vendas.parquet')" in to_sql(compile_chain(a, "n1", for_display=True).query())


def test_lru_eviction_by_size(tmp_path: Path) -> None:
    cache = MaterializedCache(tmp_path, max_bytes=10)
    old, new = tmp_path / "a.parquet", tmp_path / "b.parquet"
    old.write_bytes(b"x" * 8)
    new.write_bytes(b"x" * 8)
    past = time.time() - 3600
    os.utime(old, (past, past))
    os.utime(new, (past + 60, past + 60))
    cache.evict()
    assert not old.exists()
    assert new.exists()
    assert cache.lookup("b") is not None
    assert cache.lookup("a") is None
