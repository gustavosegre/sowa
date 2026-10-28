"""Request/response models of the HTTP API (exported to TypeScript via OpenAPI)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from forja.domain.issues import Issue
from forja.domain.pipeline import Pipeline
from forja.domain.schema import Column
from forja.domain.types import LogicalType
from forja.io.models import Detection, ImportOptions, ImportReport


class ApiError(BaseModel):
    code: str
    message: str
    hint: str | None = None
    detail: str | None = None
    issues: list[Issue] = []


# ---------------------------------------------------------------- projects


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    pipeline: Pipeline | None = None


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectOut(BaseModel):
    id: str
    name: str
    version: int
    created_at: datetime
    updated_at: datetime
    node_count: int = 0


class VersionOut(BaseModel):
    id: int
    version: int
    label: str | None
    node_count: int
    created_at: datetime


class VersionDetail(VersionOut):
    pipeline: Pipeline


class VersionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)


class SavedPipeline(BaseModel):
    pipeline: Pipeline
    version: int
    updated_at: datetime


# ---------------------------------------------------------------- pipeline


class PipelineRequest(BaseModel):
    pipeline: Pipeline


class NodeRequest(PipelineRequest):
    node_id: str


class NodeAnalysisOut(BaseModel):
    status: Literal["ok", "warning", "error", "blocked"]
    columns: list[Column] | None
    issues: list[Issue]
    changed_columns: list[str] = []
    input_columns: dict[str, list[Column]] = {}
    hash: str | None = None


class SchemaResponse(BaseModel):
    nodes: dict[str, NodeAnalysisOut]


class PreviewRequest(NodeRequest):
    limit: int = Field(default=500, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)


class StatsOut(BaseModel):
    row_count: int | None
    input_row_counts: dict[str, int]
    issues: list[Issue]


class ProfileRequest(NodeRequest):
    column: str


class ProfileBucket(BaseModel):
    from_: float | str = Field(alias="from")
    to: float | str
    count: int

    model_config = {"populate_by_name": True}


class ProfileTop(BaseModel):
    value: str | None
    count: int


class ProfileOut(BaseModel):
    column: str
    type: LogicalType
    rows: int
    total_rows: int
    sampled: bool
    nulls: int
    null_pct: float
    distinct: int
    min: str | None
    max: str | None
    mean: float | None
    top: list[ProfileTop]
    histogram: list[ProfileBucket]


class SqlOut(BaseModel):
    sql: str


class DistinctRequest(NodeRequest):
    column: str
    limit: int = Field(default=200, ge=1, le=10_000)
    of_input: bool = True  # values from the node's input (pivot config) rather than its output
    date_group: Literal["none", "year", "quarter", "month", "day"] = "none"
    # Values as the text the pivot compiler compares against (CAST AS VARCHAR).
    as_text: bool = False


class DistinctOut(BaseModel):
    values: list[Any]
    truncated: bool


# ---------------------------------------------------------------- formulas


class FormulaCheckRequest(BaseModel):
    formula: str
    locale: Literal["pt-BR", "en-US"] = "pt-BR"
    context: Literal["row", "aggregate"] = "row"
    group_keys: list[str] = []
    # Either the pipeline + node whose *input* the formula reads, or explicit columns.
    pipeline: Pipeline | None = None
    node_id: str | None = None
    columns: list[Column] | None = None


class FormulaCheckOut(BaseModel):
    ok: bool
    type: LogicalType | None = None
    type_label: str | None = None
    issues: list[Issue] = []
    examples: list[str | None] = []
    columns: list[str] = []


class FunctionParamOut(BaseModel):
    name: str
    type: str
    optional: bool
    variadic: bool


class FunctionOut(BaseModel):
    name: str
    aliases: list[str]
    category: str
    context: Literal["row", "aggregate"]
    signature: str
    signature_en: str
    params: list[FunctionParamOut]
    returns: str | None
    description: str
    example: str
    excel: bool


class FormulaRenderRequest(BaseModel):
    formula: str
    from_locale: Literal["pt-BR", "en-US"]
    to_locale: Literal["pt-BR", "en-US"]


# ---------------------------------------------------------------- sources


class SourceOut(BaseModel):
    id: str
    project_id: str | None
    name: str
    filename: str
    format: str
    size_bytes: int
    status: str
    row_count: int | None
    columns: list[Column] | None
    options: ImportOptions | None
    error: str | None
    created_at: datetime


class UploadOut(BaseModel):
    source: SourceOut
    detection: Detection | None
    error: ApiError | None = None


class DetectRequest(BaseModel):
    options: ImportOptions


class ConfirmOut(BaseModel):
    source: SourceOut
    report: ImportReport


class SourceRename(BaseModel):
    name: str = Field(min_length=1, max_length=300)


# ---------------------------------------------------------------- exports


class ExportRequest(NodeRequest):
    project_id: str | None = None


class ExportJobOut(BaseModel):
    id: str
    node_id: str
    status: Literal["pending", "running", "done", "error"]
    progress: float
    format: str
    filename: str
    rows: int | None
    size_bytes: int | None
    error: Issue | None
    created_at: datetime
    finished_at: datetime | None


# ---------------------------------------------------------------- node catalog


class NodeTypeOut(BaseModel):
    type: str
    label: str
    category: str
    description: str
    inputs: list[str]
    variadic_inputs: bool
    has_output: bool
    annotation: bool
    config_schema: dict[str, Any]
