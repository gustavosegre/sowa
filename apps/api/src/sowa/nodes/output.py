from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error, fmt_int, warning
from sowa.domain.schema import Schema
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, QueryRunner, count_star, project
from sowa.nodes.registry import register_node

XLSX_MAX_ROWS = 1_048_576
XLSX_MAX_COLS = 16_384


class CsvExportOptions(BaseModel):
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: Literal["utf-8", "utf-8-sig", "latin-1"] = "utf-8"
    decimal_separator: Literal[".", ","] = "."
    date_format: str = "%Y-%m-%d"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    header: bool = True
    quote: str = Field(default='"', max_length=1)


EXCEL_BR = CsvExportOptions(
    delimiter=";",
    encoding="utf-8-sig",
    decimal_separator=",",
    date_format="%d/%m/%Y",
    datetime_format="%d/%m/%Y %H:%M:%S",
)


class ParquetOptions(BaseModel):
    compression: Literal["zstd", "snappy", "none"] = "zstd"
    row_group_size: int | None = Field(default=None, ge=1000)
    # Hive-style partitions (coluna=valor/…); the download is a .zip of the folder.
    partition_by: list[str] = []


class OutputConfig(NodeConfig):
    format: Literal["csv", "parquet", "xlsx", "json", "ndjson"] = "csv"
    filename: str = "dataset"
    preset: Literal["excel_br", "custom"] | None = None
    csv: CsvExportOptions = CsvExportOptions()
    parquet: ParquetOptions = ParquetOptions()

    def csv_options(self) -> CsvExportOptions:
        return EXCEL_BR if self.preset == "excel_br" else self.csv


@register_node
class OutputNode(NodeSpec[OutputConfig]):
    type = "output"
    config_model = OutputConfig
    label = "Exportar"
    category = "output"
    description = "Gera o dataset final em CSV, Parquet, XLSX ou JSON."
    has_output = False

    def validate(self, cfg: OutputConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        issues: list[Issue] = []
        if not cfg.filename.strip() or any(ch in cfg.filename for ch in '\\/:*?"<>|'):
            issues.append(
                error(
                    IssueCode.INVALID_CONFIG,
                    "Nome de arquivo inválido.",
                    hint='Use letras, números, espaço, "-" e "_".',
                )
            )
        for c in cfg.parquet.partition_by if cfg.format == "parquet" else []:
            if not inputs["in"].has(c):
                issues.append(column_not_found(c, where=ctx.input_labels.get("in")))
        if cfg.format == "parquet" and cfg.parquet.partition_by and len(cfg.parquet.partition_by) >= len(inputs["in"]):
            issues.append(
                error(IssueCode.INVALID_CONFIG, "Particionar por todas as colunas deixaria os arquivos sem dados.")
            )
        if cfg.format == "xlsx" and len(inputs["in"]) > XLSX_MAX_COLS:
            issues.append(
                error(
                    IssueCode.XLSX_LIMIT,
                    f"O XLSX aceita no máximo {fmt_int(XLSX_MAX_COLS)} colunas; o dataset tem "
                    f"{fmt_int(len(inputs['in']))}.",
                    hint="Exporte em CSV ou Parquet.",
                )
            )
        return issues

    def compile(
        self, cfg: OutputConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        return inputs["in"].copy()

    def runtime_issues(
        self,
        cfg: OutputConfig,
        inputs: dict[str, exp.Select],
        output: exp.Select,
        schemas: dict[str, Schema],
        ctx: NodeContext,
        run: QueryRunner,
    ) -> list[Issue]:
        if cfg.format != "xlsx":
            return []
        n = int(run(project(inputs["in"], [count_star()]))[0][0])
        if n + 1 > XLSX_MAX_ROWS:
            return [
                warning(
                    IssueCode.XLSX_LIMIT,
                    f"O dataset tem {fmt_int(n)} linhas, mais do que o limite do Excel "
                    f"({fmt_int(XLSX_MAX_ROWS - 1)} linhas de dados).",
                    hint="Exporte em CSV ou Parquet, ou filtre/agrupe antes.",
                    count=n,
                )
            ]
        return []
