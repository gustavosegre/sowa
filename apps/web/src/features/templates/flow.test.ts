import { beforeEach, describe, expect, it } from "vitest";

import type { Pipeline, PipelineNode } from "@/api/types";
import { EMPTY_PIPELINE, usePipelineStore } from "@/stores/pipelineStore";

import { flowFromSelection } from "./flow";

const node = (id: string, type: string, x = 0, label?: string): PipelineNode => ({
  id,
  type,
  config: {},
  ui: { x, y: 100, ...(label ? { label } : {}) },
});
const edge = (source: string, target: string, target_handle = "in") => ({
  id: `${source}-${target}-${target_handle}`,
  source,
  source_handle: "out",
  target,
  target_handle,
});

// src -> cast -> calc -> out ;  other -> join(right), cast -> join(left)
const P: Pipeline = {
  ...EMPTY_PIPELINE,
  nodes: [
    node("src", "source", 0, "Vendas"),
    node("other", "source", 0, "Clientes"),
    node("cast", "cast", 300),
    node("calc", "calculated", 600),
    node("join", "join", 600),
    node("out", "output", 900),
  ],
  edges: [
    edge("src", "cast"),
    edge("cast", "calc"),
    edge("calc", "out"),
    edge("cast", "join", "left"),
    edge("other", "join", "right"),
  ],
};
const label = (id: string) => P.nodes.find((n) => n.id === id)?.ui.label ?? id;

describe("flowFromSelection", () => {
  it("turns outside edges into inputs and finds the single output", () => {
    const flow = flowFromSelection(P, ["cast", "calc"], label);
    expect(flow.nodes.map((n) => [n.id, n.ui.x])).toEqual([
      ["cast", 0],
      ["calc", 300],
    ]);
    expect(flow.edges.map((e) => e.id)).toEqual(["cast-calc-in"]);
    expect(flow.inputs).toEqual([{ name: "Vendas", targets: [{ node: "cast", handle: "in" }] }]);
    expect(flow.output).toBe("calc");
  });

  it("one input per outside node; no single output when two branches end", () => {
    const flow = flowFromSelection(P, ["cast", "calc", "join"], label);
    expect(flow.inputs.map((i) => i.name)).toEqual(["Vendas", "Clientes"]);
    expect(flow.inputs[1]?.targets).toEqual([{ node: "join", handle: "right" }]);
    expect(flow.output).toBeNull();
  });
});

describe("store: templates", () => {
  beforeEach(() => usePipelineStore.getState().load(structuredClone(P)));

  it("inserts a flow wired to the given source", () => {
    const flow = flowFromSelection(P, ["cast", "calc"], label);
    const ids = usePipelineStore.getState().insertFlow(flow, { at: { x: 0, y: 500 }, sources: ["other"] });
    const { pipeline, selectedId } = usePipelineStore.getState();
    expect(ids).toHaveLength(2);
    const [cast, calc] = ids;
    expect(pipeline.edges.some((e) => e.source === "other" && e.target === cast)).toBe(true);
    expect(pipeline.edges.some((e) => e.source === cast && e.target === calc)).toBe(true);
    expect(selectedId).toBe(calc);
  });

  it("expands a sub-flow node in place, keeping its connections", () => {
    const flow = flowFromSelection(P, ["cast", "calc"], label);
    const st = usePipelineStore.getState();
    st.load({
      ...EMPTY_PIPELINE,
      nodes: [
        node("src", "source"),
        { ...node("sub", "subflow", 300), config: { flow } },
        node("out", "output", 600),
      ],
      edges: [edge("src", "sub", "in_0"), edge("sub", "out")],
    });
    const ids = usePipelineStore.getState().expandSubflow("sub", flow);
    const p = usePipelineStore.getState().pipeline;
    expect(p.nodes.map((n) => n.id)).not.toContain("sub");
    const [cast, calc] = ids;
    expect(p.edges.map((e) => [e.source, e.target])).toEqual(
      expect.arrayContaining([
        ["src", cast],
        [cast, calc],
        [calc, "out"],
      ]),
    );
    expect(p.edges).toHaveLength(3);
    // The node after the sub-flow moved right to make room for the extra step.
    expect(p.nodes.find((n) => n.id === "out")?.ui.x).toBe(900);
  });
});
