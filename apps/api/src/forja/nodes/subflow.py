"""Sub-flow: a saved template embedded as one node (CLAUDE.md §19, Fase 3).

The config carries a snapshot of the template's flow, so the pipeline stays
self-contained (and its hash covers the inner nodes). The inside is analyzed as
a pipeline of its own: each flow input becomes a `subflow_input` node that reads
the outer table (a `Slot`), and inner node ids are prefixed with the outer node
id so their CTEs never shadow the outer ones.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field
from sqlglot import exp

from forja.compiler.analyze import Analysis, Describer, NodeResult, analyze
from forja.compiler.build import Chain, compile_chain, cte_ref
from forja.domain.issues import Issue, IssueCode, error
from forja.domain.pipeline import CURRENT_SCHEMA_VERSION, Edge, Flow, Node, NodeUI, Pipeline, PipelineSettings
from forja.domain.schema import Schema
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, QueryRunner, Slot, ident
from forja.nodes.registry import register_node

# Node types that make no sense inside a sub-flow (they read or write files).
FORBIDDEN = {"source": "Fonte", "output": "Exportar"}


class SubflowInputConfig(NodeConfig):
    slot: int = Field(ge=0)


@register_node
class SubflowInputNode(NodeSpec[SubflowInputConfig]):
    type = "subflow_input"
    config_model = SubflowInputConfig
    label = "Entrada do sub-fluxo"
    category = "input"
    inputs = ()
    internal = True

    def validate(self, cfg: SubflowInputConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        if cfg.slot >= len(ctx.slots):
            return [error(IssueCode.SUBFLOW_INVALID, "Esta entrada só existe dentro de um sub-fluxo.")]
        return []

    def infer_schema(self, cfg: SubflowInputConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        return ctx.slots[cfg.slot].schema

    def compile(
        self, cfg: SubflowInputConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        return exp.select(exp.Star()).from_(exp.Table(this=ident(ctx.slots[cfg.slot].ref)))


class SubflowConfig(NodeConfig):
    template_id: str | None = None
    template_name: str = ""
    template_version: int = 0
    flow: Flow = Flow()


def _label(r: NodeResult) -> str:
    return r.node.ui.label or (r.spec.label if r.spec else r.node.type)


def _prefixed(issue: Issue, r: NodeResult) -> Issue:
    return issue.model_copy(update={"node_id": None, "position": None, "message": f'Em "{_label(r)}": {issue.message}'})


def _inner_describer(ctx: NodeContext) -> Describer | None:
    """DESCRIBE inside the sub-flow: inner CTEs, then the outer chain (via the outer describer)."""
    outer = ctx.describe
    if outer is None:
        return None

    def describe(inner: Analysis, upstream: list[str], query: exp.Select) -> Schema:
        ctes: list[tuple[str, exp.Select]] = []
        seen: set[str] = set()
        for up in upstream:
            for name, sel in compile_chain(inner, up).ctes:
                if name not in seen:
                    seen.add(name)
                    ctes.append((name, sel))
        return outer(Chain(target="", ctes=ctes).wrap(query))

    return describe


def _within(run: QueryRunner, chain: Chain) -> QueryRunner:
    """Runner for an inner node: inner CTEs first, then the outer runner adds the outer ones."""
    return lambda q: run(chain.wrap(q))


@register_node
class SubflowNode(NodeSpec[SubflowConfig]):
    type = "subflow"
    config_model = SubflowConfig
    label = "Sub-fluxo"
    category = "advanced"
    description = "Um template salvo usado como um único nó"
    inputs = ("in_0",)
    variadic_inputs = True

    def input_handles(self, connected: Sequence[str], cfg: SubflowConfig) -> tuple[str, ...]:
        return tuple(f"in_{k}" for k in range(len(cfg.flow.inputs)))

    def _structure_issues(self, cfg: SubflowConfig) -> list[Issue]:
        flow = cfg.flow
        ids = {n.id for n in flow.nodes}
        out: list[Issue] = []
        for n in flow.nodes:
            if n.type in FORBIDDEN:
                out.append(
                    error(
                        IssueCode.SUBFLOW_INVALID,
                        f'Sub-fluxos não podem conter o nó "{FORBIDDEN[n.type]}".',
                        hint="Insira o template como nós editáveis.",
                    )
                )
        if not flow.inputs:
            out.append(
                error(
                    IssueCode.SUBFLOW_INVALID,
                    "O template não tem entradas.",
                    hint="Salve o template a partir de nós que recebem dados de fora da seleção.",
                )
            )
        if flow.output is None or flow.output not in ids:
            out.append(
                error(
                    IssueCode.SUBFLOW_INVALID,
                    "O template não tem uma saída única.",
                    hint="Um sub-fluxo precisa terminar em um só nó. Insira o template como nós editáveis.",
                )
            )
        if any(t.node not in ids for i in flow.inputs for t in i.targets):
            out.append(error(IssueCode.SUBFLOW_INVALID, "Uma entrada do template aponta para um nó que não existe."))
        return out

    def _expand(self, cfg: SubflowConfig, ctx: NodeContext, schemas: dict[str, Schema]) -> Analysis:
        prefix = f"{ctx.node_id}/"
        flow = cfg.flow
        # model_construct: prefixed ids may exceed the user-facing id limit.
        nodes = [Node.model_construct(id=prefix + n.id, type=n.type, config=n.config, ui=n.ui) for n in flow.nodes]
        edges = [
            Edge.model_construct(
                id=prefix + e.id,
                source=prefix + e.source,
                target=prefix + e.target,
                source_handle=e.source_handle,
                target_handle=e.target_handle,
            )
            for e in flow.edges
        ]
        slots: list[Slot] = []
        for k, inp in enumerate(flow.inputs):
            sid = f"{prefix}__in{k}"
            ui = NodeUI(label=inp.name)
            nodes.append(Node.model_construct(id=sid, type="subflow_input", config={"slot": k}, ui=ui))
            edges += [
                Edge.model_construct(
                    id=f"{sid}/e{i}", source=sid, target=prefix + t.node, source_handle="out", target_handle=t.handle
                )
                for i, t in enumerate(inp.targets)
            ]
            slots.append(Slot(schema=schemas[f"in_{k}"], ref=ctx.input_ids.get(f"in_{k}", "")))
        p = Pipeline.model_construct(
            schema_version=CURRENT_SCHEMA_VERSION,
            settings=PipelineSettings(locale=flow.locale, params=ctx.params),
            nodes=nodes,
            edges=edges,
        )
        return analyze(p, ctx.sources, _inner_describer(ctx), slots)

    def validate(self, cfg: SubflowConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        found = self._structure_issues(cfg)
        if found:
            return found
        inner = self._expand(cfg, ctx, inputs)
        return [
            _prefixed(i, r)
            for r in inner.results.values()
            for i in r.issues
            if i.severity != "info" and r.node.type != "subflow_input"
        ]

    def infer_schema(self, cfg: SubflowConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        inner = self._expand(cfg, ctx, inputs)
        schema = inner.results[f"{ctx.node_id}/{cfg.flow.output}"].schema
        assert schema is not None
        return schema

    def compile(
        self, cfg: SubflowConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        inner = self._expand(cfg, ctx, schemas)
        return compile_chain(inner, f"{ctx.node_id}/{cfg.flow.output}", for_display=ctx.for_display).query()

    def runtime_issues(
        self,
        cfg: SubflowConfig,
        inputs: dict[str, exp.Select],
        output: exp.Select,
        schemas: dict[str, Schema],
        ctx: NodeContext,
        run: QueryRunner,
    ) -> list[Issue]:
        """Data-dependent warnings of the inner nodes (cast failures, division by zero…)."""
        inner = self._expand(cfg, ctx, schemas)
        out: list[Issue] = []
        for nid in inner.graph.order:
            r = inner.results[nid]
            if r.spec is None or r.config is None or not r.ok or r.spec.annotation:
                continue
            if type(r.spec).runtime_issues is NodeSpec.runtime_issues:
                continue
            chain = compile_chain(inner, nid, keep_inputs=True)
            in_schemas = {h: s for h, u in r.inputs.items() if (s := inner.results[u].schema) is not None}
            found = r.spec.runtime_issues(
                r.config,
                {h: cte_ref(u) for h, u in r.inputs.items()},
                cte_ref(nid),
                in_schemas,
                inner.context(nid),
                _within(run, chain),
            )
            out += [_prefixed(i, r) for i in found]
        return out
