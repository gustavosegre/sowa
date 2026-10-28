"""Node contract (CLAUDE.md §8.3).

A node spec is stateless. `compile` is pure: config + input selects -> select.
"""

from __future__ import annotations

import builtins
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict
from sqlglot import exp

from forja.domain.issues import Issue
from forja.domain.pipeline import Parameter
from forja.domain.schema import Schema
from forja.domain.types import LogicalType

Category = Literal["input", "columns", "rows", "aggregate", "combine", "output", "advanced", "organize"]


class NodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


C = TypeVar("C", bound=NodeConfig)


@dataclass(frozen=True)
class SourceInfo:
    id: str
    name: str
    status: str  # "pending" | "ready" | "error"
    parquet_path: str | None
    schema: Schema
    row_count: int | None
    sha256: str | None


class SourceResolver(Protocol):
    def get(self, source_id: str) -> SourceInfo | None: ...


@dataclass(frozen=True)
class Slot:
    """An outside table visible inside a sub-flow: its schema and the outer CTE that holds it."""

    schema: Schema
    ref: str


class _NoSources:
    def get(self, source_id: str) -> SourceInfo | None:
        return None


@dataclass
class NodeContext:
    node_id: str
    node_label: str
    locale: str = "pt-BR"
    sources: SourceResolver = field(default_factory=_NoSources)
    # Labels of upstream nodes per input handle (for error messages).
    input_labels: dict[str, str] = field(default_factory=dict)
    # When true, compile for display ("Copiar como SQL"): no absolute server paths.
    for_display: bool = False
    params: list[Parameter] = field(default_factory=list)
    # Upstream node id per input handle.
    input_ids: dict[str, str] = field(default_factory=dict)
    # Schema of a query over the inputs, asked to the engine (bind only). Used by the SQL node.
    describe: Callable[[exp.Select], Schema] | None = None
    # Inside a sub-flow: the outer tables feeding it (read by `subflow_input`).
    slots: list[Slot] = field(default_factory=list)

    def param(self, name: str) -> Parameter | None:
        return next((p for p in self.params if p.name == name), None)


# A function that runs a SELECT and returns its rows (used for data-dependent warnings).
QueryRunner = Callable[[exp.Select], list[tuple[Any, ...]]]


class NodeSpec(Generic[C]):
    type: ClassVar[str]
    config_model: ClassVar[builtins.type[NodeConfig]]
    label: ClassVar[str]
    category: ClassVar[Category]
    description: ClassVar[str] = ""
    inputs: ClassVar[tuple[str, ...]] = ("in",)
    # Nodes like `union` accept in_0 … in_n.
    variadic_inputs: ClassVar[bool] = False
    has_output: ClassVar[bool] = True
    cacheable: ClassVar[bool] = False
    # Annotation nodes (note, frame) have no data semantics at all.
    annotation: ClassVar[bool] = False
    # Internal nodes (sub-flow plumbing) aren't offered in the catalog.
    internal: ClassVar[bool] = False

    def validate(self, cfg: C, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        return []

    def infer_schema(self, cfg: C, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        return inputs["in"]

    def compile(
        self, cfg: C, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        raise NotImplementedError

    def runtime_issues(
        self,
        cfg: C,
        inputs: dict[str, exp.Select],
        output: exp.Select,
        schemas: dict[str, Schema],
        ctx: NodeContext,
        run: QueryRunner,
    ) -> list[Issue]:
        """Warnings that need data (cast failures, division by zero…). Optional."""
        return []

    def input_handles(self, connected: Sequence[str], cfg: C) -> tuple[str, ...]:
        if self.variadic_inputs:
            return tuple(sorted(connected, key=lambda h: int(h.split("_")[1]) if "_" in h else 0))
        return self.inputs


# ------------------------------------------------------------------ SQL helpers


def ident(name: str) -> exp.Identifier:
    return exp.to_identifier(name, quoted=True)


def col(name: str, table: str | None = None) -> exp.Column:
    return exp.Column(this=ident(name), table=ident(table) if table else None)


def alias(e: exp.Expr, name: str) -> exp.Alias:
    return exp.Alias(this=e, alias=ident(name))


def lit(v: str | int | float | bool | None) -> exp.Expr:
    if v is None:
        return exp.Null()
    if isinstance(v, bool):
        return exp.Boolean(this=v)
    if isinstance(v, (int, float)):
        return exp.Literal.number(v)
    return exp.Literal.string(v)


def from_input(sel: exp.Select) -> exp.Expr:
    """The FROM source of an input select (`SELECT * FROM "cte"`)."""
    return sel.args["from_"].this.copy()  # type: ignore[no-any-return]


def project(inp: exp.Select, exprs: Sequence[exp.Expr]) -> exp.Select:
    return exp.select(*exprs).from_(from_input(inp))


def count_star() -> exp.Expr:
    return exp.Count(this=exp.Star())


def cast_to(e: exp.Expr, t: LogicalType) -> exp.Expr:
    from forja.domain.types import to_duckdb

    return exp.Cast(this=e, to=to_duckdb(t))
