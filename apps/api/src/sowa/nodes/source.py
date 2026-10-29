from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, error
from sowa.domain.schema import Schema
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, SourceInfo, lit
from sowa.nodes.registry import register_node


class SampleConfig(BaseModel):
    mode: Literal["first", "random"] = "first"
    rows: int = Field(default=10_000, ge=1, le=10_000_000)
    seed: int = 42


class SourceConfig(NodeConfig):
    source_id: str = ""
    sample: SampleConfig | None = None


@register_node
class SourceNode(NodeSpec[SourceConfig]):
    type = "source"
    config_model = SourceConfig
    label = "Fonte"
    category = "input"
    description = "Lê um arquivo importado."
    inputs = ()

    def _source(self, cfg: SourceConfig, ctx: NodeContext) -> SourceInfo | None:
        return ctx.sources.get(cfg.source_id) if cfg.source_id else None

    def validate(self, cfg: SourceConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        if not cfg.source_id:
            return [
                error(
                    IssueCode.SOURCE_NOT_FOUND,
                    "Escolha um arquivo para esta fonte.",
                    hint="Faça upload de um arquivo ou selecione um já importado.",
                )
            ]
        src = self._source(cfg, ctx)
        if src is None:
            return [
                error(
                    IssueCode.SOURCE_NOT_FOUND,
                    "O arquivo desta fonte não foi encontrado. Ele pode ter sido removido.",
                    hint="Selecione outro arquivo ou faça upload novamente.",
                )
            ]
        if src.status != "ready" or not src.parquet_path:
            return [
                error(
                    IssueCode.SOURCE_NOT_READY,
                    f'O arquivo "{src.name}" ainda não terminou de ser importado.',
                    hint="Conclua o assistente de importação.",
                )
            ]
        return []

    def infer_schema(self, cfg: SourceConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        src = self._source(cfg, ctx)
        assert src is not None
        return src.schema

    def compile(
        self, cfg: SourceConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        src = self._source(cfg, ctx)
        assert src is not None
        assert src.parquet_path is not None
        path = f"{src.name}.parquet" if ctx.for_display else src.parquet_path
        table: exp.Expr = exp.Table(this=exp.Anonymous(this="read_parquet", expressions=[lit(path)]))
        sel = exp.select(exp.Star()).from_(table)
        if cfg.sample is not None:
            if cfg.sample.mode == "first":
                sel = sel.limit(cfg.sample.rows)
            else:
                sample = exp.TableSample(
                    method=exp.var("RESERVOIR"),
                    size=exp.Literal.number(cfg.sample.rows),
                    seed=exp.Literal.number(cfg.sample.seed),
                )
                sel.set("sample", sample)
        return sel
