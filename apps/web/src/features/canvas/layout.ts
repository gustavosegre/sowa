import ELK from "elkjs/lib/elk.bundled.js";

import type { Pipeline } from "@/api/types";

const elk = new ELK();

/** Auto-layout (left to right) of data nodes with elkjs. Annotations keep their positions. */
export async function autoLayout(
  p: Pipeline,
  sizes: Record<string, { width: number; height: number }>,
): Promise<Record<string, { x: number; y: number }>> {
  const nodes = p.nodes.filter((n) => n.type !== "note" && n.type !== "frame");
  const ids = new Set(nodes.map((n) => n.id));
  const graph = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.layered.spacing.nodeNodeBetweenLayers": "80",
      "elk.spacing.nodeNode": "40",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
    },
    children: nodes.map((n) => ({
      id: n.id,
      width: sizes[n.id]?.width ?? 240,
      height: sizes[n.id]?.height ?? 90,
    })),
    edges: p.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  };
  const res = await elk.layout(graph);
  const out: Record<string, { x: number; y: number }> = {};
  for (const c of res.children ?? []) out[c.id] = { x: (c.x ?? 0) + 40, y: (c.y ?? 0) + 40 };
  return out;
}
