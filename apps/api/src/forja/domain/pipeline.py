"""The pipeline: a declarative graph of nodes (JSON). See CLAUDE.md §8.1.

Node configs are kept as raw dicts here and validated per node type by the
node registry, so that one broken node becomes a visible issue on that node
instead of rejecting the whole graph.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CURRENT_SCHEMA_VERSION = 1


class NodeUI(BaseModel):
    model_config = ConfigDict(extra="allow")

    x: float = 0
    y: float = 0
    label: str | None = None
    color: str | None = None
    width: float | None = None
    height: float | None = None


class Node(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: str
    config: dict[str, Any] = {}
    ui: NodeUI = NodeUI()

    def display_name(self) -> str:
        return self.ui.label or self.id


class Edge(BaseModel):
    id: str
    source: str
    target: str
    source_handle: str = "out"
    target_handle: str = "in"


class PipelineSettings(BaseModel):
    locale: Literal["pt-BR", "en-US"] = "pt-BR"


class Pipeline(BaseModel):
    schema_version: int = CURRENT_SCHEMA_VERSION
    settings: PipelineSettings = PipelineSettings()
    nodes: list[Node] = []
    edges: list[Edge] = []

    def node(self, node_id: str) -> Node | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None
