/**
 * The server sees a debounced copy of the pipeline, so typing in a config field
 * doesn't fire a request per keystroke. Everything that asks the server about
 * the graph (schema, preview, stats) reads `useServerPipeline`.
 */
import { useEffect } from "react";
import { create } from "zustand";

import { useSchema } from "@/api/hooks";
import type { Column, NodeAnalysis, Pipeline } from "@/api/types";
import { EMPTY_PIPELINE, usePipelineStore } from "@/stores/pipelineStore";

interface ServerPipelineState {
  pipeline: Pipeline;
  set: (p: Pipeline) => void;
}

export const useServerPipeline = create<ServerPipelineState>()((set) => ({
  pipeline: EMPTY_PIPELINE,
  set: (pipeline) => set({ pipeline }),
}));

/** Mount once in the editor: mirrors the store into the debounced server pipeline. */
export function useSyncServerPipeline(delayMs = 250): void {
  const pipeline = usePipelineStore((s) => s.pipeline);
  const setServer = useServerPipeline((s) => s.set);
  useEffect(() => {
    const h = setTimeout(() => setServer(pipeline), delayMs);
    return () => clearTimeout(h);
  }, [pipeline, setServer, delayMs]);
}

export function useAnalysis() {
  const pipeline = useServerPipeline((s) => s.pipeline);
  return useSchema(pipeline);
}

export function useNodeAnalysis(nodeId: string | null | undefined): NodeAnalysis | undefined {
  const { data } = useAnalysis();
  return nodeId ? data?.nodes[nodeId] : undefined;
}

/** Columns available at a node's input handle (what its config can reference). */
export function useInputColumns(nodeId: string, handle = "in"): Column[] {
  const a = useNodeAnalysis(nodeId);
  return a?.input_columns[handle] ?? [];
}
