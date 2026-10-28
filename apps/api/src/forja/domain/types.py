"""Logical column types shown to the user and their DuckDB counterparts."""

from __future__ import annotations

import re
from enum import StrEnum

from sqlglot import exp


class LogicalType(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    # Types DuckDB can produce that the user cannot pick directly (e.g. LIST from Parquet).
    OTHER = "other"


TYPE_LABELS: dict[LogicalType, str] = {
    LogicalType.TEXT: "Texto",
    LogicalType.INTEGER: "Inteiro",
    LogicalType.DECIMAL: "Decimal",
    LogicalType.BOOLEAN: "Booleano",
    LogicalType.DATE: "Data",
    LogicalType.DATETIME: "Data e hora",
    LogicalType.TIME: "Hora",
    LogicalType.OTHER: "Outro",
}

_DUCKDB_NAMES: dict[LogicalType, str] = {
    LogicalType.TEXT: "VARCHAR",
    LogicalType.INTEGER: "BIGINT",
    LogicalType.DECIMAL: "DOUBLE",
    LogicalType.BOOLEAN: "BOOLEAN",
    LogicalType.DATE: "DATE",
    LogicalType.DATETIME: "TIMESTAMP",
    LogicalType.TIME: "TIME",
    LogicalType.OTHER: "VARCHAR",
}

NUMERIC_TYPES = frozenset({LogicalType.INTEGER, LogicalType.DECIMAL})
TEMPORAL_TYPES = frozenset({LogicalType.DATE, LogicalType.DATETIME})


def label(t: LogicalType) -> str:
    return TYPE_LABELS[t]


def to_duckdb(t: LogicalType, precision: int | None = None, scale: int | None = None) -> exp.DataType:
    if t is LogicalType.DECIMAL and precision is not None:
        return exp.DataType.build(f"DECIMAL({precision}, {scale or 0})", dialect="duckdb")
    return exp.DataType.build(_DUCKDB_NAMES[t], dialect="duckdb")


_INTEGER_RE = re.compile(r"^(U?(TINY|SMALL|BIG|HUGE)?INT(EGER)?\d*|INT\d+|LONG|SHORT)$")


def from_duckdb(type_name: str) -> LogicalType:
    """Map a DuckDB type name (as reported by the engine) to a logical type."""
    t = type_name.strip().upper()
    if t in ("VARCHAR", "TEXT", "STRING", "UUID", "BLOB") or t.startswith("VARCHAR") or t.startswith("ENUM"):
        return LogicalType.TEXT
    if _INTEGER_RE.match(t):
        return LogicalType.INTEGER
    if t in ("DOUBLE", "FLOAT", "REAL", "FLOAT4", "FLOAT8") or t.startswith("DECIMAL") or t.startswith("NUMERIC"):
        return LogicalType.DECIMAL
    if t in ("BOOLEAN", "BOOL"):
        return LogicalType.BOOLEAN
    if t == "DATE":
        return LogicalType.DATE
    if t.startswith("TIMESTAMP") or t == "DATETIME":
        return LogicalType.DATETIME
    if t.startswith("TIME"):
        return LogicalType.TIME
    return LogicalType.OTHER


def unify(a: LogicalType, b: LogicalType) -> LogicalType | None:
    """Common supertype of two logical types, or None when incompatible."""
    if a == b:
        return a
    if {a, b} <= NUMERIC_TYPES:
        return LogicalType.DECIMAL
    if {a, b} <= TEMPORAL_TYPES:
        return LogicalType.DATETIME
    return None
