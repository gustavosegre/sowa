import { describe, expect, it } from "vitest";

import type { PipelineEdge } from "@/api/types";

import { handleName, inputHandles, lastVariadicInput } from "./handles";

const edge = (target: string, handle: string): PipelineEdge => ({
  id: `${target}-${handle}`,
  source: "s",
  source_handle: "out",
  target,
  target_handle: handle,
});

describe("input handles", () => {
  it("keeps fixed handles as declared", () => {
    expect(inputHandles({ inputs: ["left", "right"] }, -1)).toEqual(["left", "right"]);
  });

  it("variadic: always one free handle after the last connected one, even with gaps", () => {
    expect(inputHandles({ inputs: ["in_0", "in_1"] }, -1)).toEqual(["in_0", "in_1"]);
    const edges = [edge("u", "in_0"), edge("u", "in_3"), edge("x", "in_9")];
    expect(lastVariadicInput(edges, "u")).toBe(3);
    expect(inputHandles({ inputs: ["in_0"] }, 3)).toEqual(["in_0", "in_1", "in_2", "in_3", "in_4"]);
  });

  it("names handles for the canvas", () => {
    expect(handleName("in")).toBeNull();
    expect(handleName("left")).toBe("esq");
    expect(handleName("in_2")).toBe("3");
  });
});
