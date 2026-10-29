"""Graph utilities: inputs per node, upstream subgraph, topological order."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from sowa.domain.pipeline import Pipeline


@dataclass
class Graph:
    order: list[str]  # topological order of nodes that are not in a cycle
    in_cycle: set[str]
    # node -> handle -> upstream node ids (more than one = misconfiguration)
    inputs: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    downstream: dict[str, list[str]] = field(default_factory=dict)


def build_graph(p: Pipeline) -> Graph:
    ids = [n.id for n in p.nodes]
    known = set(ids)
    inputs: dict[str, dict[str, list[str]]] = {i: defaultdict(list) for i in ids}
    downstream: dict[str, list[str]] = {i: [] for i in ids}
    indeg: dict[str, int] = dict.fromkeys(ids, 0)
    for e in p.edges:
        if e.source not in known or e.target not in known or e.source == e.target:
            continue
        inputs[e.target][e.target_handle].append(e.source)
        downstream[e.source].append(e.target)
        indeg[e.target] += 1
    queue = deque(i for i in ids if indeg[i] == 0)
    order: list[str] = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for d in downstream[n]:
            indeg[d] -= 1
            if indeg[d] == 0:
                queue.append(d)
    in_cycle = known - set(order)
    return Graph(order=order, in_cycle=in_cycle, inputs={k: dict(v) for k, v in inputs.items()}, downstream=downstream)


def upstream_of(g: Graph, node_id: str) -> list[str]:
    """`node_id` and everything feeding it, in topological order."""
    needed: set[str] = set()
    stack = [node_id]
    while stack:
        n = stack.pop()
        if n in needed:
            continue
        needed.add(n)
        for ups in g.inputs.get(n, {}).values():
            stack.extend(ups)
    return [n for n in g.order if n in needed]
