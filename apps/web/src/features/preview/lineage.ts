/**
 * Column lineage (CLAUDE.md §19, Fase 3): walk upstream from a node following the
 * input that carries the column, tracking renames, and report where it was
 * created, changed or read from. Uses only the static analysis (no data).
 */
import type { Pipeline, SchemaResponse, SelectConfig } from "@/api/types";
import { getMeta } from "@/features/nodes/registry";
import { t } from "@/i18n/pt-BR";

export interface LineageStep {
  nodeId: string;
  text: string;
}

const MAIN_HANDLES = ["in", "left", "main", "in_0"];

export function columnLineage(
  pipeline: Pipeline,
  analysis: SchemaResponse | undefined,
  nodeId: string,
  column: string,
  sourceName: (sourceId: string) => string | undefined,
): LineageStep[] {
  const steps: LineageStep[] = [];
  const label = (id: string) => {
    const n = pipeline.nodes.find((x) => x.id === id);
    return n?.ui.label || (n ? (getMeta(n.type)?.label ?? n.type) : id);
  };
  let current = nodeId;
  let name = column;
  for (let guard = 0; guard < 200; guard++) {
    const node = pipeline.nodes.find((n) => n.id === current);
    const a = analysis?.nodes[current];
    if (!node || !a) break;
    if (node.type === "source") {
      const file =
        sourceName(typeof node.config.source_id === "string" ? node.config.source_id : "") ?? label(current);
      steps.push({ nodeId: current, text: t.lineage.fromFile(file) });
      break;
    }
    // Which input carries the column (with its name before this node)?
    let before = name;
    if (node.type === "select") {
      const cfg = node.config as SelectConfig;
      before = Object.entries(cfg.renames).find(([, v]) => v === name)?.[0] ?? name;
      if (before !== name) steps.push({ nodeId: current, text: t.lineage.renamedIn(label(current), before) });
    }
    const inputs = a.input_columns;
    const handle =
      Object.keys(inputs).find(
        (h) => MAIN_HANDLES.includes(h) && inputs[h]?.some((c) => c.name === before),
      ) ?? Object.keys(inputs).find((h) => inputs[h]?.some((c) => c.name === before));
    if (handle === undefined) {
      steps.push({ nodeId: current, text: t.lineage.createdIn(label(current)) });
      break;
    }
    if (a.changed_columns.includes(name) && before === name) {
      steps.push({ nodeId: current, text: t.lineage.changedIn(label(current)) });
    }
    const edge = pipeline.edges.find((e) => e.target === current && e.target_handle === handle);
    if (!edge) break;
    current = edge.source;
    name = before;
  }
  return steps.reverse();
}
