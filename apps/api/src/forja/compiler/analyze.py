"""Static analysis: validate every node and infer its schema without touching data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError
from sqlglot import exp

from forja.compiler.graph import Graph, build_graph
from forja.domain.issues import Issue, IssueCode
from forja.domain.pipeline import Node, Pipeline
from forja.domain.schema import Schema
from forja.nodes.base import NodeConfig, NodeContext, NodeSpec, Slot, SourceResolver, _NoSources
from forja.nodes.registry import get_spec

Status = Literal["ok", "warning", "error", "blocked"]


@dataclass
class NodeResult:
    node: Node
    spec: NodeSpec[Any] | None
    config: NodeConfig | None
    inputs: dict[str, str]  # handle -> upstream node id
    schema: Schema | None = None
    issues: list[Issue] = field(default_factory=list)
    status: Status = "ok"
    changed_columns: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "warning")


# (analysis, upstream node ids, query over them) -> schema. Provided by the engine.
Describer = Callable[["Analysis", list[str], exp.Select], Schema]


@dataclass
class Analysis:
    pipeline: Pipeline
    graph: Graph
    results: dict[str, NodeResult]
    sources: SourceResolver
    describer: Describer | None = None
    # Set when analyzing the inside of a sub-flow.
    slots: list[Slot] = field(default_factory=list)

    def context(self, node_id: str, *, for_display: bool = False, result: NodeResult | None = None) -> NodeContext:
        r = result or self.results[node_id]
        return NodeContext(
            node_id=node_id,
            node_label=r.node.display_name(),
            locale=self.pipeline.settings.locale,
            sources=self.sources,
            input_labels={h: self.results[u].node.display_name() for h, u in r.inputs.items()},
            for_display=for_display,
            params=list(self.pipeline.settings.params),
            input_ids=dict(r.inputs),
            describe=self._describe(list(r.inputs.values())),
            slots=self.slots,
        )

    def _describe(self, upstream: list[str]) -> Callable[[exp.Select], Schema] | None:
        describer = self.describer
        if describer is None:
            return None
        return lambda q: describer(self, upstream, q)


_PYDANTIC_MESSAGES = {
    "missing": "campo obrigatório",
    "extra_forbidden": "campo desconhecido",
    "literal_error": "valor não permitido",
    "string_type": "deveria ser texto",
    "int_parsing": "deveria ser um número inteiro",
    "float_parsing": "deveria ser um número",
    "greater_than_equal": "valor muito pequeno",
    "less_than_equal": "valor muito grande",
}


def config_issues(err: ValidationError) -> list[Issue]:
    out: list[Issue] = []
    for e in err.errors()[:5]:
        loc = ".".join(str(x) for x in e["loc"]) or "configuração"
        msg = _PYDANTIC_MESSAGES.get(e["type"], e["msg"])
        out.append(
            Issue(code=IssueCode.INVALID_CONFIG, message=f'Configuração inválida em "{loc}": {msg}.', detail=e["msg"])
        )
    return out


def analyze(
    p: Pipeline,
    sources: SourceResolver | None = None,
    describer: Describer | None = None,
    slots: list[Slot] | None = None,
) -> Analysis:
    graph = build_graph(p)
    nodes = {n.id: n for n in p.nodes}
    results: dict[str, NodeResult] = {}
    analysis = Analysis(p, graph, results, sources or _NoSources(), describer, slots or [])

    for nid in graph.in_cycle:
        results[nid] = NodeResult(
            nodes[nid],
            get_spec(nodes[nid].type),
            None,
            {},
            status="error",
            issues=[
                Issue(
                    node_id=nid,
                    code=IssueCode.CYCLE,
                    message="Este nó faz parte de um ciclo: a saída volta para a própria entrada.",
                    hint="Remova uma das conexões do ciclo.",
                ),
            ],
        )

    for nid in graph.order:
        results[nid] = _analyze_node(nodes[nid], graph, analysis)
    return analysis


def _analyze_node(node: Node, graph: Graph, analysis: Analysis) -> NodeResult:
    results = analysis.results
    spec = get_spec(node.type)
    raw_inputs = graph.inputs.get(node.id, {})
    r = NodeResult(node, spec, None, {})

    def fail(*issues: Issue, status: Status = "error") -> NodeResult:
        for i in issues:
            i.node_id = node.id
        r.issues.extend(issues)
        r.status = status
        return r

    if spec is None:
        return fail(Issue(code=IssueCode.UNKNOWN_NODE_TYPE, message=f'Tipo de nó desconhecido: "{node.type}".'))
    try:
        r.config = spec.config_model.model_validate(node.config)
    except ValidationError as e:
        return fail(*config_issues(e))
    if spec.annotation:
        return r

    handles = spec.input_handles(list(raw_inputs), r.config)
    issues: list[Issue] = []
    for h in handles:
        ups = raw_inputs.get(h, [])
        if not ups:
            issues.append(
                Issue(
                    code=IssueCode.MISSING_INPUT,
                    message=_missing_input_message(spec, h),
                    hint="Conecte a saída de outro nó a esta entrada.",
                )
            )
        elif len(ups) > 1:
            issues.append(
                Issue(
                    code=IssueCode.MISSING_INPUT,
                    message="Há mais de uma conexão na mesma entrada.",
                    hint="Deixe só uma conexão por entrada.",
                )
            )
        else:
            r.inputs[h] = ups[0]
    if spec.variadic_inputs and not handles:
        issues.append(Issue(code=IssueCode.MISSING_INPUT, message="Conecte pelo menos uma tabela a este nó."))
    if issues:
        return fail(*issues)

    blocked_by = [results[u] for u in r.inputs.values() if not results[u].ok]
    if blocked_by:
        names = ", ".join(f'"{b.node.display_name()}"' for b in blocked_by)
        return fail(
            Issue(
                severity="info",
                code=IssueCode.UPSTREAM_ERROR,
                message=f"Bloqueado: há um erro no nó {names}.",
                hint="Corrija o nó anterior.",
            ),
            status="blocked",
        )

    schemas = {h: results[u].schema for h, u in r.inputs.items()}
    in_schemas: dict[str, Schema] = {h: s for h, s in schemas.items() if s is not None}
    ctx = analysis.context(node.id, result=r)
    found = spec.validate(r.config, in_schemas, ctx)
    for i in found:
        i.node_id = node.id
    r.issues.extend(found)
    if any(i.is_error for i in found):
        r.status = "error"
        return r
    r.schema = spec.infer_schema(r.config, in_schemas, ctx)
    if any(i.severity == "warning" for i in found):
        r.status = "warning"
    main = in_schemas.get("in") or in_schemas.get("left") or in_schemas.get("main") or in_schemas.get("in_0")
    if main is not None and spec.has_output:
        r.changed_columns = [c.name for c in r.schema if not main.has(c.name) or main.type_of(c.name) != c.type]
    return r


def _missing_input_message(spec: NodeSpec[Any], handle: str) -> str:
    names = {"in": "", "left": " da esquerda", "right": " da direita", "main": " principal", "lookup": " de consulta"}
    name = names.get(handle, f" {int(handle[3:]) + 1}" if handle[3:].isdigit() else f" {handle}")
    return f'O nó "{spec.label}" precisa de uma entrada{name} conectada.'
