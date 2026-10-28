from __future__ import annotations

from typing import Literal

from sqlglot import exp

from forja.domain.issues import Issue, IssueCode, column_not_found, error
from forja.domain.schema import Column, Schema
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, alias, col, project
from forja.nodes.registry import register_node


class SelectConfig(NodeConfig):
    # keep: `columns` are kept in this order. drop: `columns` are removed.
    mode: Literal["keep", "drop"] = "keep"
    columns: list[str] = []
    renames: dict[str, str] = {}


@register_node
class SelectNode(NodeSpec[SelectConfig]):
    type = "select"
    config_model = SelectConfig
    label = "Selecionar colunas"
    category = "columns"
    description = "Escolher, reordenar, renomear e remover colunas."

    def _kept(self, cfg: SelectConfig, schema: Schema) -> list[Column]:
        if cfg.mode == "keep":
            return [c for name in cfg.columns if (c := schema.get(name)) is not None]
        dropped = set(cfg.columns)
        return [c for c in schema if c.name not in dropped]

    def validate(self, cfg: SelectConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        schema = inputs["in"]
        issues: list[Issue] = []
        for name in cfg.columns:
            if not schema.has(name):
                issues.append(column_not_found(name, where=ctx.input_labels.get("in")))
        if len(set(cfg.columns)) != len(cfg.columns):
            issues.append(error(IssueCode.DUPLICATE_COLUMN, "Há colunas repetidas na seleção."))
        kept = self._kept(cfg, schema)
        kept_names = {c.name for c in kept}
        for old, new in cfg.renames.items():
            if not schema.has(old):
                issues.append(column_not_found(old, where=ctx.input_labels.get("in")))
            elif old not in kept_names:
                continue
            if not new.strip():
                issues.append(error(IssueCode.EMPTY_NAME, f'O novo nome da coluna "{old}" está vazio.', column=old))
        if not kept and not issues:
            issues.append(
                error(
                    IssueCode.NO_COLUMNS,
                    "Nenhuma coluna selecionada.",
                    hint="Escolha pelo menos uma coluna para manter.",
                )
            )
        out_names = [cfg.renames.get(c.name, c.name) for c in kept]
        seen: set[str] = set()
        for n in out_names:
            if n in seen:
                issues.append(
                    error(
                        IssueCode.DUPLICATE_COLUMN,
                        f'Duas colunas ficariam com o nome "{n}".',
                        column=n,
                        hint="Use nomes diferentes ao renomear.",
                    )
                )
            seen.add(n)
        return issues

    def infer_schema(self, cfg: SelectConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        return Schema(
            columns=[Column(name=cfg.renames.get(c.name, c.name), type=c.type) for c in self._kept(cfg, inputs["in"])]
        )

    def compile(
        self, cfg: SelectConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        exprs: list[exp.Expr] = []
        for c in self._kept(cfg, schemas["in"]):
            new = cfg.renames.get(c.name, c.name)
            exprs.append(col(c.name) if new == c.name else alias(col(c.name), new))
        return project(inputs["in"], exprs)
