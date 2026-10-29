from __future__ import annotations

from typing import Literal

from pydantic import Field
from sqlglot import exp

from sowa.domain.schema import Schema
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, from_input, lit
from sowa.nodes.registry import register_node


class SampleNodeConfig(NodeConfig):
    mode: Literal["first", "random", "percent"] = "first"
    rows: int = Field(default=1000, ge=1)
    percent: float = Field(default=10.0, gt=0, le=100)
    seed: int = 42


@register_node
class SampleNode(NodeSpec[SampleNodeConfig]):
    type = "sample"
    config_model = SampleNodeConfig
    label = "Amostra / Limite"
    category = "rows"
    description = "Primeiras N linhas, N linhas aleatórias ou uma porcentagem (com semente)."

    def compile(
        self, cfg: SampleNodeConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        sel = exp.select(exp.Star()).from_(from_input(inputs["in"]))
        if cfg.mode == "first":
            return sel.limit(cfg.rows)
        if cfg.mode == "random":
            sample = exp.TableSample(method=exp.var("RESERVOIR"), size=lit(cfg.rows), seed=lit(cfg.seed))
        else:
            sample = exp.TableSample(method=exp.var("BERNOULLI"), percent=lit(cfg.percent), seed=lit(cfg.seed))
        sel.set("sample", sample)
        return sel
