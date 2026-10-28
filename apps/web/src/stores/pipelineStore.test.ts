import { beforeEach, describe, expect, it } from "vitest";

import type { Pipeline } from "@/api/types";

import { EMPTY_PIPELINE, redo, undo, usePipelineStore } from "./pipelineStore";

const store = () => usePipelineStore.getState();
const edges = () => store().pipeline.edges.map((e) => `${e.source}->${e.target}:${e.target_handle}`);

function chain(): Pipeline {
  return {
    ...EMPTY_PIPELINE,
    nodes: [
      { id: "a", type: "source", config: { source_id: "s" }, ui: { x: 0, y: 0 } },
      { id: "b", type: "filter", config: {}, ui: { x: 300, y: 0 } },
      { id: "c", type: "sort", config: { keys: [] }, ui: { x: 600, y: 0 } },
    ],
    edges: [
      { id: "e1", source: "a", target: "b", source_handle: "out", target_handle: "in" },
      { id: "e2", source: "b", target: "c", source_handle: "out", target_handle: "in" },
    ],
  };
}

describe("pipelineStore", () => {
  beforeEach(() => store().load(chain()));

  it("adds a node with the type's default config", () => {
    const id = store().addNode("calculated");
    const n = store().pipeline.nodes.find((x) => x.id === id);
    expect(n?.config).toEqual({ name: "nova_coluna", mode: "new", formula: "" });
    expect(store().selectedId).toBe(id);
  });

  it("inserts a node in the middle of an edge", () => {
    const id = store().insertOnEdge("e1", "cast");
    expect(id).not.toBeNull();
    expect(edges()).toEqual(["b->c:in", `a->${id}:in`, `${id}->b:in`]);
  });

  it("inserts after a node, keeping the chain and making room downstream", () => {
    const id = store().addNode("select", { after: "a" });
    expect(edges()).toContain(`a->${id}:in`);
    expect(edges()).toContain(`${id}->b:in`);
    expect(edges()).not.toContain("a->b:in");
    const b = store().pipeline.nodes.find((n) => n.id === "b");
    expect(b?.ui.x).toBe(590);
  });

  it("reconnects the neighbours when a node is removed", () => {
    store().removeNodes(["b"]);
    expect(edges()).toEqual(["a->c:in"]);
    expect(store().pipeline.nodes.map((n) => n.id)).toEqual(["a", "c"]);
  });

  it("keeps one connection per input handle", () => {
    store().addNode("source", { position: { x: 0, y: 300 } });
    const other = store().pipeline.nodes.at(-1)?.id ?? "";
    store().connect(other, "b", "in");
    expect(edges().filter((e) => e.endsWith("->b:in"))).toEqual([`${other}->b:in`]);
  });

  it("undoes and redoes graph changes but not selection", () => {
    store().updateConfig("c", {
      keys: [{ column: "x", direction: "desc", nulls: "last", case_sensitive: false }],
    });
    store().select("a");
    undo();
    expect(store().pipeline.nodes.find((n) => n.id === "c")?.config).toEqual({ keys: [] });
    expect(store().selectedId).toBe("a");
    redo();
    expect((store().pipeline.nodes.find((n) => n.id === "c")?.config.keys as unknown[]).length).toBe(1);
  });

  it("loading a pipeline clears the history", () => {
    store().removeNodes(["c"]);
    store().load(chain());
    undo();
    expect(store().pipeline.nodes).toHaveLength(3);
  });

  it("pastes nodes with new ids and internal edges only", () => {
    const { pipeline } = store();
    const ids = store().paste({
      kind: "forja/nodes",
      nodes: pipeline.nodes.slice(0, 2),
      edges: pipeline.edges,
    });
    expect(ids).toHaveLength(2);
    expect(ids).not.toContain("a");
    expect(edges()).toContain(`${ids[0] ?? ""}->${ids[1] ?? ""}:in`);
    expect(store().pipeline.nodes).toHaveLength(5);
  });

  it("switching locale replaces formulas in one undoable step", () => {
    store().setLocale("en-US", { b: { mode: "formula", formula: "[x] > 1.5" } });
    expect(store().pipeline.settings.locale).toBe("en-US");
    undo();
    expect(store().pipeline.settings.locale).toBe("pt-BR");
    expect(store().pipeline.nodes.find((n) => n.id === "b")?.config).toEqual({});
  });

  it("does not place a new node on top of another", () => {
    const id = store().addNode("note", { position: { x: 0, y: 0 } });
    const n = store().pipeline.nodes.find((x) => x.id === id);
    expect(n?.ui.y).toBeGreaterThan(100);
  });
});
