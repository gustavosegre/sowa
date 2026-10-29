"""Test helpers shared by unit, golden and contract tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sowa.compiler.analyze import Analysis
from sowa.compiler.build import compile_chain
from sowa.domain.pipeline import Pipeline
from sowa.domain.schema import Column, Schema
from sowa.domain.types import from_duckdb
from sowa.engine.duck import Engine
from sowa.nodes.base import SourceInfo

FILES = Path(__file__).parent / "fixtures" / "files"


class FakeSources:
    def __init__(self) -> None:
        self.items: dict[str, SourceInfo] = {}

    def get(self, source_id: str) -> SourceInfo | None:
        return self.items.get(source_id)


def pipeline(nodes: list[dict[str, Any]], edges: list[tuple[str, str] | tuple[str, str, str]]) -> Pipeline:
    return Pipeline.model_validate(
        {
            "nodes": nodes,
            "edges": [
                {"id": f"e{i}", "source": e[0], "target": e[1], "target_handle": e[2] if len(e) > 2 else "in"}
                for i, e in enumerate(edges)
            ],
        }
    )


def chain_of(*nodes: dict[str, Any]) -> Pipeline:
    """Linear pipeline n0 -> n1 -> ... from node dicts (ids assigned automatically)."""
    full = [{"id": f"n{i}", **n} for i, n in enumerate(nodes)]
    return pipeline(full, [(f"n{i}", f"n{i + 1}") for i in range(len(full) - 1)])


def run(engine: Engine, a: Analysis, node_id: str) -> list[tuple[Any, ...]]:
    return engine.rows(compile_chain(a, node_id).query())


def actual_schema(engine: Engine, a: Analysis, node_id: str) -> Schema:
    q = compile_chain(a, node_id).query()
    rows = engine.rows(f"DESCRIBE {q.sql(dialect='duckdb', identify=True)}")
    return Schema(columns=[Column(name=str(r[0]), type=from_duckdb(str(r[1]))) for r in rows])


def src(name: str = "vendas") -> dict[str, Any]:
    return {"type": "source", "config": {"source_id": name}}
