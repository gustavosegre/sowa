"""Static schema of a node's output (names + logical types, in order)."""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel

from sowa.domain.types import LogicalType


class Column(BaseModel):
    name: str
    type: LogicalType


class Schema(BaseModel):
    columns: list[Column] = []

    @classmethod
    def of(cls, *cols: tuple[str, LogicalType]) -> Schema:
        return cls(columns=[Column(name=n, type=t) for n, t in cols])

    def __iter__(self) -> Iterator[Column]:  # type: ignore[override]
        return iter(self.columns)

    def __len__(self) -> int:
        return len(self.columns)

    @property
    def names(self) -> list[str]:
        return [c.name for c in self.columns]

    def get(self, name: str) -> Column | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def has(self, name: str) -> bool:
        return self.get(name) is not None

    def type_of(self, name: str) -> LogicalType:
        col = self.get(name)
        if col is None:
            raise KeyError(name)
        return col.type
