"""Locale-neutral formula AST. Positions are character offsets in the source text."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class _Node(BaseModel):
    start: int
    end: int


class NumberLit(_Node):
    kind: Literal["number"] = "number"
    value: str  # canonical text with "." as decimal separator
    is_integer: bool


class StringLit(_Node):
    kind: Literal["string"] = "string"
    value: str


class BoolLit(_Node):
    kind: Literal["bool"] = "bool"
    value: bool


class ColumnRef(_Node):
    kind: Literal["column"] = "column"
    name: str


class ParamRef(_Node):
    kind: Literal["param"] = "param"
    name: str


class Call(_Node):
    kind: Literal["call"] = "call"
    name: str  # as typed by the user
    args: list[Expr]


class Unary(_Node):
    kind: Literal["unary"] = "unary"
    op: Literal["-", "+"]
    operand: Expr


class Binary(_Node):
    kind: Literal["binary"] = "binary"
    op: Literal["+", "-", "*", "/", "^", "&", "=", "<>", "<", ">", "<=", ">="]
    left: Expr
    right: Expr


class Percent(_Node):
    kind: Literal["percent"] = "percent"
    operand: Expr


Expr = Annotated[
    NumberLit | StringLit | BoolLit | ColumnRef | ParamRef | Call | Unary | Binary | Percent,
    Field(discriminator="kind"),
]

Call.model_rebuild()
Unary.model_rebuild()
Binary.model_rebuild()
Percent.model_rebuild()
