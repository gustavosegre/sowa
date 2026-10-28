/** Input handles of a node type, shared by the canvas card and the inputs picker. */
import type { PipelineEdge } from "@/api/types";

import type { NodeMeta } from "./types";

const HANDLE_LABELS: Record<string, string> = {
  left: "esq",
  right: "dir",
  main: "principal",
  lookup: "consulta",
};

/** Short name shown next to a handle ("esq", "2"…); null for the single `in`. */
export function handleName(handle: string): string | null {
  return HANDLE_LABELS[handle] ?? (handle.startsWith("in_") ? String(Number(handle.slice(3)) + 1) : null);
}

/** Highest connected `in_<i>` index of a node, -1 when none (a number keeps store selectors stable). */
export function lastVariadicInput(edges: PipelineEdge[], nodeId: string): number {
  let last = -1;
  for (const e of edges) {
    if (e.target === nodeId && e.target_handle.startsWith("in_")) {
      last = Math.max(last, Number(e.target_handle.slice(3)));
    }
  }
  return last;
}

/** Variadic inputs (union, sql): up to the last connected one plus one free handle. */
export function inputHandles(meta: Pick<NodeMeta, "inputs">, lastConnected: number): string[] {
  if (!meta.inputs[0]?.startsWith("in_")) return meta.inputs;
  const n = Math.max(meta.inputs.length, lastConnected + 2);
  return Array.from({ length: n }, (_, i) => `in_${i}`);
}
