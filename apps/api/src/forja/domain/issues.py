"""User-facing errors and warnings. Codes are stable; messages are pt-BR."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class IssueCode(StrEnum):
    # Graph structure
    CYCLE = "CYCLE"
    MISSING_INPUT = "MISSING_INPUT"
    UNKNOWN_NODE_TYPE = "UNKNOWN_NODE_TYPE"
    INVALID_CONFIG = "INVALID_CONFIG"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    NODE_NOT_FOUND = "NODE_NOT_FOUND"
    # Columns
    COLUMN_NOT_FOUND = "COLUMN_NOT_FOUND"
    DUPLICATE_COLUMN = "DUPLICATE_COLUMN"
    EMPTY_NAME = "EMPTY_NAME"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    NO_COLUMNS = "NO_COLUMNS"
    # Sources
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    SOURCE_NOT_READY = "SOURCE_NOT_READY"
    # Formulas
    FORMULA_SYNTAX = "FORMULA_SYNTAX"
    FORMULA_TYPE = "FORMULA_TYPE"
    FORMULA_UNKNOWN_FUNCTION = "FORMULA_UNKNOWN_FUNCTION"
    FORMULA_ARGUMENTS = "FORMULA_ARGUMENTS"
    FORMULA_CONTEXT = "FORMULA_CONTEXT"
    # Runtime warnings
    CAST_FAILURES = "CAST_FAILURES"
    DIVISION_BY_ZERO = "DIVISION_BY_ZERO"
    JOIN_ROW_MULTIPLICATION = "JOIN_ROW_MULTIPLICATION"
    PIVOT_NEW_VALUES = "PIVOT_NEW_VALUES"
    PIVOT_TOO_MANY_VALUES = "PIVOT_TOO_MANY_VALUES"
    XLSX_LIMIT = "XLSX_LIMIT"
    LOOKUP_MULTIPLE_MATCHES = "LOOKUP_MULTIPLE_MATCHES"
    # Engine
    TIMEOUT = "TIMEOUT"
    ENGINE_ERROR = "ENGINE_ERROR"
    SQL_NOT_ALLOWED = "SQL_NOT_ALLOWED"


Severity = Literal["error", "warning", "info"]


class Position(BaseModel):
    start: int
    end: int


class Issue(BaseModel):
    node_id: str | None = None
    severity: Severity = "error"
    code: IssueCode
    column: str | None = None
    message: str
    hint: str | None = None
    detail: str | None = None
    position: Position | None = None
    count: int | None = None
    examples: list[str] | None = None

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


def error(
    code: IssueCode,
    message: str,
    *,
    column: str | None = None,
    hint: str | None = None,
    position: Position | None = None,
    detail: str | None = None,
) -> Issue:
    return Issue(code=code, message=message, column=column, hint=hint, position=position, detail=detail)


def warning(
    code: IssueCode,
    message: str,
    *,
    column: str | None = None,
    hint: str | None = None,
    count: int | None = None,
    examples: list[str] | None = None,
) -> Issue:
    return Issue(
        severity="warning", code=code, message=message, column=column, hint=hint, count=count, examples=examples
    )


def column_not_found(column: str, *, where: str | None = None) -> Issue:
    origin = f' no nó "{where}"' if where else " na entrada deste nó"
    return error(
        IssueCode.COLUMN_NOT_FOUND,
        f'A coluna "{column}" não existe{origin}. Ela pode ter sido renomeada ou removida em um nó anterior.',
        column=column,
        hint="Escolha outra coluna ou desfaça a alteração no nó anterior.",
    )


def fmt_int(n: int) -> str:
    """Format an integer with pt-BR thousands separator."""
    return f"{n:,}".replace(",", ".")


def plural(n: int, singular: str, plural_: str) -> str:
    """E.g. `1 valor`, `1.234 valores`."""
    return f"{fmt_int(n)} {singular if n == 1 else plural_}"


def fmt_dec(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
