/**
 * The graph only changes through these actions (CLAUDE.md §17): undo/redo and
 * autosave depend on it. Selection lives here too but is not part of history.
 */
import { temporal } from "zundo";
import { create } from "zustand";

import type { Parameter, Pipeline, PipelineEdge, PipelineNode } from "@/api/types";
import { getMeta } from "@/features/nodes/registry";
import { uid } from "@/lib/utils";

export type Locale = "pt-BR" | "en-US";
type Config = Record<string, unknown>;
interface XY {
  x: number;
  y: number;
}

export const EMPTY_PIPELINE: Pipeline = {
  schema_version: 1,
  settings: { locale: "pt-BR", params: [] },
  nodes: [],
  edges: [],
};

export interface ClipboardPayload {
  kind: "forja/nodes";
  nodes: PipelineNode[];
  edges: PipelineEdge[];
}

interface State {
  pipeline: Pipeline;
  selectedId: string | null;

  load: (p: Pipeline) => void;
  select: (id: string | null) => void;
  addNode: (
    type: string,
    opts?: { position?: XY; config?: Config; label?: string; after?: string | null; connectFrom?: string },
  ) => string;
  updateConfig: (id: string, update: Config | ((c: Config) => Config)) => void;
  setLabel: (id: string, label: string) => void;
  setUi: (id: string, ui: Partial<PipelineNode["ui"]>) => void;
  movePositions: (positions: Record<string, XY>) => void;
  removeNodes: (ids: string[]) => void;
  connect: (source: string, target: string, targetHandle: string) => void;
  removeEdges: (ids: string[]) => void;
  insertOnEdge: (edgeId: string, type: string, position?: XY) => string | null;
  duplicate: (ids: string[]) => string[];
  paste: (payload: ClipboardPayload, offset?: XY) => string[];
  /** Switch the formula locale; `configs` carries the node configs with re-rendered formulas. */
  setLocale: (locale: Locale, configs?: Record<string, Config>) => void;
  setParams: (params: Parameter[]) => void;
}

function nodeAt(p: Pipeline, id: string): PipelineNode | undefined {
  return p.nodes.find((n) => n.id === id);
}

const CARD_W = 250;
const CARD_H = 110;

/** First position at or below `p` that doesn't overlap an existing data node. */
function freeSpot(pipeline: Pipeline, p: XY): XY {
  const pos = { ...p };
  const taken = pipeline.nodes.filter((n) => n.type !== "frame");
  for (let i = 0; i < 50; i++) {
    const hit = taken.some((n) => Math.abs(n.ui.x - pos.x) < CARD_W && Math.abs(n.ui.y - pos.y) < CARD_H);
    if (!hit) return pos;
    pos.y += CARD_H + 20;
  }
  return pos;
}

function shiftDownstream(pipeline: Pipeline, from: string, dx: number): Pipeline {
  const seen = new Set<string>();
  const stack = pipeline.edges.filter((e) => e.source === from).map((e) => e.target);
  while (stack.length) {
    const id = stack.pop() ?? "";
    if (seen.has(id)) continue;
    seen.add(id);
    for (const e of pipeline.edges) if (e.source === id) stack.push(e.target);
  }
  if (!seen.size) return pipeline;
  return {
    ...pipeline,
    nodes: pipeline.nodes.map((n) => (seen.has(n.id) ? { ...n, ui: { ...n.ui, x: n.ui.x + dx } } : n)),
  };
}

function defaultConfig(type: string): Config {
  return getMeta(type)?.defaultConfig() ?? {};
}

function edge(source: string, target: string, targetHandle = "in"): PipelineEdge {
  return { id: uid("e"), source, target, source_handle: "out", target_handle: targetHandle };
}

function firstInput(type: string): string | null {
  const meta = getMeta(type);
  if (!meta) return "in";
  return meta.inputs[0] ?? null;
}

export const usePipelineStore = create<State>()(
  temporal(
    (set, get) => ({
      pipeline: EMPTY_PIPELINE,
      selectedId: null,

      load: (p) => {
        set({ pipeline: p, selectedId: null });
        usePipelineStore.temporal.getState().clear();
      },

      select: (id) => set({ selectedId: id }),

      addNode: (type, opts = {}) => {
        const id = uid("n");
        let { pipeline } = get();
        const after = opts.after ? nodeAt(pipeline, opts.after) : undefined;
        const from = after ?? (opts.connectFrom ? nodeAt(pipeline, opts.connectFrom) : undefined);
        const position = freeSpot(
          pipeline,
          opts.position ??
            (from
              ? { x: from.ui.x + 290, y: from.ui.y }
              : { x: 80 + (pipeline.nodes.length % 4) * 40, y: 80 + pipeline.nodes.length * 30 }),
        );
        if (after) {
          // Make room: shift everything downstream of `after` to the right.
          pipeline = shiftDownstream(pipeline, after.id, 290);
        }
        const node: PipelineNode = {
          id,
          type,
          config: { ...defaultConfig(type), ...(opts.config ?? {}) },
          ui: { ...position, ...(opts.label ? { label: opts.label } : {}) },
        };
        let edges = pipeline.edges;
        const handle = firstInput(type);
        if (after && handle) {
          // Insert into the chain: after -> new -> previous targets of `after`.
          const outgoing = edges.filter((e) => e.source === after.id);
          edges = edges.filter((e) => e.source !== after.id);
          edges = [
            ...edges,
            edge(after.id, id, handle),
            ...outgoing.map((e) => ({ ...e, id: uid("e"), source: id })),
          ];
        } else if (opts.connectFrom && handle) {
          edges = [...edges, edge(opts.connectFrom, id, handle)];
        }
        set({ pipeline: { ...pipeline, nodes: [...pipeline.nodes, node], edges }, selectedId: id });
        return id;
      },

      updateConfig: (id, update) =>
        set(({ pipeline }) => ({
          pipeline: {
            ...pipeline,
            nodes: pipeline.nodes.map((n) =>
              n.id === id ? { ...n, config: typeof update === "function" ? update(n.config) : update } : n,
            ),
          },
        })),

      setLabel: (id, label) =>
        set(({ pipeline }) => ({
          pipeline: {
            ...pipeline,
            nodes: pipeline.nodes.map((n) =>
              n.id === id ? { ...n, ui: { ...n.ui, label: label.trim() ? label : null } } : n,
            ),
          },
        })),

      setUi: (id, ui) =>
        set(({ pipeline }) => ({
          pipeline: {
            ...pipeline,
            nodes: pipeline.nodes.map((n) => (n.id === id ? { ...n, ui: { ...n.ui, ...ui } } : n)),
          },
        })),

      movePositions: (positions) =>
        set(({ pipeline }) => ({
          pipeline: {
            ...pipeline,
            nodes: pipeline.nodes.map((n) => {
              const p = positions[n.id];
              return p ? { ...n, ui: { ...n.ui, x: Math.round(p.x), y: Math.round(p.y) } } : n;
            }),
          },
        })),

      removeNodes: (ids) =>
        set(({ pipeline, selectedId }) => {
          const removed = new Set(ids);
          let edges = pipeline.edges;
          for (const id of ids) {
            // Reconnect: single input -> every output target.
            const ins = edges.filter((e) => e.target === id && !removed.has(e.source));
            const outs = edges.filter((e) => e.source === id && !removed.has(e.target));
            edges = edges.filter((e) => e.source !== id && e.target !== id);
            const only = ins.length === 1 ? ins[0] : undefined;
            if (only) {
              for (const o of outs) {
                const taken = edges.some((e) => e.target === o.target && e.target_handle === o.target_handle);
                if (!taken) edges.push({ ...o, id: uid("e"), source: only.source });
              }
            }
          }
          return {
            pipeline: { ...pipeline, nodes: pipeline.nodes.filter((n) => !removed.has(n.id)), edges },
            selectedId: selectedId && removed.has(selectedId) ? null : selectedId,
          };
        }),

      connect: (source, target, targetHandle) =>
        set(({ pipeline }) => {
          if (source === target) return {};
          // One connection per input handle: the new one replaces the old.
          const edges = pipeline.edges.filter(
            (e) => !(e.target === target && e.target_handle === targetHandle),
          );
          return { pipeline: { ...pipeline, edges: [...edges, edge(source, target, targetHandle)] } };
        }),

      removeEdges: (ids) =>
        set(({ pipeline }) => ({
          pipeline: { ...pipeline, edges: pipeline.edges.filter((e) => !ids.includes(e.id)) },
        })),

      insertOnEdge: (edgeId, type, position) => {
        const { pipeline } = get();
        const e = pipeline.edges.find((x) => x.id === edgeId);
        const handle = firstInput(type);
        if (!e || !handle) return null;
        const src = nodeAt(pipeline, e.source);
        const dst = nodeAt(pipeline, e.target);
        const id = uid("n");
        const pos = position ?? {
          x: ((src?.ui.x ?? 0) + (dst?.ui.x ?? 0)) / 2,
          y: ((src?.ui.y ?? 0) + (dst?.ui.y ?? 0)) / 2 + 40,
        };
        const node: PipelineNode = { id, type, config: defaultConfig(type), ui: { x: pos.x, y: pos.y } };
        const edges = pipeline.edges
          .filter((x) => x.id !== edgeId)
          .concat([edge(e.source, id, handle), { ...e, id: uid("e"), source: id }]);
        set({ pipeline: { ...pipeline, nodes: [...pipeline.nodes, node], edges }, selectedId: id });
        return id;
      },

      duplicate: (ids) => {
        const { pipeline } = get();
        const nodes = pipeline.nodes.filter((n) => ids.includes(n.id));
        const edges = pipeline.edges.filter((e) => ids.includes(e.source) && ids.includes(e.target));
        return get().paste({ kind: "forja/nodes", nodes, edges }, { x: 40, y: 40 });
      },

      paste: (payload, offset = { x: 40, y: 40 }) => {
        // Move the whole group down until it doesn't cover existing nodes.
        const existing = get().pipeline;
        const off = { ...offset };
        for (let i = 0; i < 30; i++) {
          const hit = payload.nodes.some((n) => {
            const p = { x: n.ui.x + off.x, y: n.ui.y + off.y };
            return freeSpot(existing, p).y !== p.y;
          });
          if (!hit) break;
          off.y += CARD_H + 20;
        }
        offset = off;
        const map = new Map<string, string>();
        const nodes = payload.nodes.map((n) => {
          const id = uid("n");
          map.set(n.id, id);
          return { ...structuredClone(n), id, ui: { ...n.ui, x: n.ui.x + offset.x, y: n.ui.y + offset.y } };
        });
        const edges = payload.edges
          .filter((e) => map.has(e.source) && map.has(e.target))
          .map((e) => ({
            ...e,
            id: uid("e"),
            source: map.get(e.source) ?? "",
            target: map.get(e.target) ?? "",
          }));
        set(({ pipeline }) => ({
          pipeline: {
            ...pipeline,
            nodes: [...pipeline.nodes, ...nodes],
            edges: [...pipeline.edges, ...edges],
          },
          selectedId: nodes[0]?.id ?? null,
        }));
        return nodes.map((n) => n.id);
      },

      setParams: (params) =>
        set(({ pipeline }) => ({ pipeline: { ...pipeline, settings: { ...pipeline.settings, params } } })),

      setLocale: (locale, configs = {}) =>
        set(({ pipeline }) => ({
          pipeline: {
            ...pipeline,
            settings: { ...pipeline.settings, locale },
            nodes: pipeline.nodes.map((n) =>
              configs[n.id] ? { ...n, config: configs[n.id] ?? n.config } : n,
            ),
          },
        })),
    }),
    {
      partialize: (s) => ({ pipeline: s.pipeline }),
      equality: (a, b) => a.pipeline === b.pipeline,
      limit: 200,
    },
  ),
);

export const undo = () => usePipelineStore.temporal.getState().undo();
export const redo = () => usePipelineStore.temporal.getState().redo();

export function selectedNode(s: State): PipelineNode | undefined {
  return s.selectedId ? s.pipeline.nodes.find((n) => n.id === s.selectedId) : undefined;
}
