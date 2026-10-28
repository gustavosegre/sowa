/**
 * Templates (CLAUDE.md §19, Fase 3): a reusable piece of the graph. Pure helpers to cut a
 * selection out of the pipeline as a `Flow` and to place a `Flow` back into one.
 */
import type { Flow, FlowInput, Pipeline, PipelineEdge, PipelineNode } from "@/api/types";
import { getMeta } from "@/features/nodes/registry";
import { uid } from "@/lib/utils";

interface XY {
  x: number;
  y: number;
}

/**
 * The selected nodes as a flow. Edges entering the selection become inputs (one per
 * outside node, named after it); the output is the only data node with no edge to
 * another selected node, or null when there isn't exactly one.
 */
export function flowFromSelection(
  pipeline: Pipeline,
  ids: string[],
  labelOf: (nodeId: string) => string,
): Flow {
  const inside = new Set(ids);
  const nodes = pipeline.nodes.filter((n) => inside.has(n.id));
  const minX = Math.min(...nodes.map((n) => n.ui.x));
  const minY = Math.min(...nodes.map((n) => n.ui.y));
  const edges = pipeline.edges.filter((e) => inside.has(e.source) && inside.has(e.target));

  const inputs: FlowInput[] = [];
  const bySource = new Map<string, FlowInput>();
  const used = new Map<string, number>();
  for (const e of pipeline.edges) {
    if (inside.has(e.source) || !inside.has(e.target)) continue;
    let inp = bySource.get(e.source);
    if (!inp) {
      const base = labelOf(e.source);
      const n = (used.get(base) ?? 0) + 1;
      used.set(base, n);
      inp = { name: n > 1 ? `${base} (${n})` : base, targets: [] };
      bySource.set(e.source, inp);
      inputs.push(inp);
    }
    inp.targets.push({ node: e.target, handle: e.target_handle });
  }

  const ends = nodes.filter((n) => {
    const m = getMeta(n.type);
    return m?.hasOutput && !m.annotation && !edges.some((e) => e.source === n.id);
  });
  return {
    locale: pipeline.settings.locale,
    nodes: nodes.map((n) => ({ ...structuredClone(n), ui: { ...n.ui, x: n.ui.x - minX, y: n.ui.y - minY } })),
    edges: edges.map((e) => ({ ...e })),
    inputs,
    output: ends.length === 1 ? (ends[0]?.id ?? null) : null,
  };
}

/** Width of a flow on the canvas (its positions start at 0). */
export function flowWidth(flow: Flow): number {
  return Math.max(0, ...flow.nodes.map((n) => n.ui.x)) + 290;
}

/**
 * New nodes/edges for `flow` placed at `at`, with fresh ids. `sources[k]` (if any) is
 * the node that feeds input k. `map` goes from flow node ids to the new ids.
 */
export function placeFlow(
  flow: Flow,
  at: XY,
  sources: (string | null | undefined)[] = [],
): { nodes: PipelineNode[]; edges: PipelineEdge[]; map: Map<string, string> } {
  const map = new Map<string, string>();
  const nodes = flow.nodes.map((n) => {
    const id = uid("n");
    map.set(n.id, id);
    return { ...structuredClone(n), id, ui: { ...n.ui, x: n.ui.x + at.x, y: n.ui.y + at.y } };
  });
  const edges: PipelineEdge[] = flow.edges
    .filter((e) => map.has(e.source) && map.has(e.target))
    .map((e) => ({ ...e, id: uid("e"), source: map.get(e.source) ?? "", target: map.get(e.target) ?? "" }));
  flow.inputs.forEach((inp, k) => {
    const src = sources[k];
    if (!src) return;
    for (const tg of inp.targets) {
      const target = map.get(tg.node);
      if (target) {
        edges.push({ id: uid("e"), source: src, source_handle: "out", target, target_handle: tg.handle });
      }
    }
  });
  return { nodes, edges, map };
}
