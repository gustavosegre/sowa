import type { Column, PipelineNode } from "@/api/types";

export interface ConfigPanelProps<C> {
  node: PipelineNode;
  config: C;
  /** Updates the node config through the store (undoable, autosaved). */
  update: (next: C | ((c: C) => C)) => void;
  /** Columns at the node's main input. */
  columns: Column[];
}
