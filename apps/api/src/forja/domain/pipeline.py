"""The pipeline: a declarative graph of nodes (JSON). See CLAUDE.md §8.1.

Node configs are kept as raw dicts here and validated per node type by the
node registry, so that one broken node becomes a visible issue on that node
instead of rejecting the whole graph.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from forja.domain.types import LogicalType

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


ParamValue = str | int | float | bool | None


class Parameter(BaseModel):
    """Global parameter, referenced as {name} in formulas and filter values."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[^{}\[\]]+$")
    type: LogicalType = LogicalType.TEXT
    value: ParamValue = None


class PipelineSettings(BaseModel):
    locale: Literal["pt-BR", "en-US"] = "pt-BR"
    params: list[Parameter] = []


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


class FlowTarget(BaseModel):
    node: str
    handle: str = "in"


class FlowInput(BaseModel):
    """An entry point of a reusable flow: the outside table feeds these node inputs."""

    name: str = Field(min_length=1, max_length=200)
    targets: list[FlowTarget] = Field(min_length=1)


class Flow(BaseModel):
    """A reusable piece of a pipeline (templates and sub-flows).

    Edges that came from outside the piece become `inputs`; `output` is the node whose
    result the piece returns (None when it has no single output, e.g. it ends in exports).
    Formulas are text in `locale`.
    """

    locale: Literal["pt-BR", "en-US"] = "pt-BR"
    nodes: list[Node] = []
    edges: list[Edge] = []
    inputs: list[FlowInput] = []
    output: str | None = None
