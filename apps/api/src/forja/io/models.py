"""Import options exchanged with the 3-step import wizard."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from forja.domain.types import LogicalType

FileFormat = Literal["csv", "parquet", "xlsx", "json", "ndjson"]


class CsvImportOptions(BaseModel):
    encoding: str = "utf-8"
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    quote: str = Field(default='"', max_length=1)
    header: bool = True
    skip_rows: int = Field(default=0, ge=0)
    decimal_separator: Literal[",", "."] = "."
    date_format: str | None = None


class XlsxOptions(BaseModel):
    sheet: str | None = None
    # Excel-style range to read, e.g. "B3:F200", "B3:F" (to the last row) or "B:F" (whole columns).
    cell_range: str | None = Field(default=None, max_length=20)
    header: bool = True
    skip_rows: int = Field(default=0, ge=0)


class ColumnPlan(BaseModel):
    source: str  # column name as read from the file (after dedup)
    name: str  # final name
    type: LogicalType = LogicalType.TEXT
    format: str | None = None  # date/time format
    decimal_separator: Literal[",", "."] | None = None
    include: bool = True


class ImportOptions(BaseModel):
    format: FileFormat
    csv: CsvImportOptions | None = None
    xlsx: XlsxOptions | None = None
    columns: list[ColumnPlan] = []


class ColumnGuess(BaseModel):
    name: str
    original_type: LogicalType
    suggested_type: LogicalType
    format: str | None = None
    decimal_separator: Literal[",", "."] | None = None
    examples: list[str | None] = []


class Detection(BaseModel):
    options: ImportOptions
    columns: list[ColumnGuess]
    sample_rows: list[list[str | None]]
    sheets: list[str] = []
    encoding_confidence: float | None = None
    notes: list[str] = []


class ImportReport(BaseModel):
    row_count: int
    failures: dict[str, int] = {}
