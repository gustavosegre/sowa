/**
 * Direct manipulation in the grid creates nodes (CLAUDE.md §1, §14): the action
 * goes right after the selected node, or into it when it already has that type.
 */
import type {
  CalculatedConfig,
  CastConfig,
  Condition,
  FilterConfig,
  GroupByConfig,
  LogicalType,
  SelectConfig,
  SortConfig,
} from "@/api/types";
import { newRule } from "@/features/nodes/cast/ConfigPanel";
import { newCondition } from "@/features/nodes/filter/ConfigPanel";
import { newAgg } from "@/features/nodes/group_by/ConfigPanel";
import { newSortKey } from "@/features/nodes/sort/ConfigPanel";
import { usePipelineStore } from "@/stores/pipelineStore";

function selected() {
  const s = usePipelineStore.getState();
  const node = s.pipeline.nodes.find((n) => n.id === s.selectedId);
  return { store: s, node };
}

/** A select node shows renamed columns; its config refers to the original names. */
function originalName(cfg: SelectConfig, shown: string): string {
  return Object.entries(cfg.renames).find(([, v]) => v === shown)?.[0] ?? shown;
}

export function changeType(column: string, from: LogicalType, to: LogicalType): void {
  const { store, node } = selected();
  if (!node) return;
  const rule = newRule(column, to, from);
  if (node.type === "cast") {
    store.updateConfig(node.id, (c) => {
      const cfg = c as CastConfig;
      return { ...cfg, casts: [...cfg.casts.filter((r) => r.column !== column), rule] };
    });
    return;
  }
  store.addNode("cast", { after: node.id, config: { casts: [rule] } satisfies CastConfig });
}

export function renameColumn(column: string, to: string): void {
  const { store, node } = selected();
  if (!node || !to.trim() || to === column) return;
  if (node.type === "select") {
    store.updateConfig(node.id, (c) => {
      const cfg = c as SelectConfig;
      return { ...cfg, renames: { ...cfg.renames, [originalName(cfg, column)]: to } };
    });
    return;
  }
  store.addNode("select", {
    after: node.id,
    config: { mode: "drop", columns: [], renames: { [column]: to } } satisfies SelectConfig,
  });
}

export function removeColumn(column: string): void {
  const { store, node } = selected();
  if (!node) return;
  if (node.type === "select" && (node.config as SelectConfig).mode === "drop") {
    store.updateConfig(node.id, (c) => {
      const cfg = c as SelectConfig;
      return { ...cfg, columns: [...cfg.columns, originalName(cfg, column)] };
    });
    return;
  }
  store.addNode("select", {
    after: node.id,
    config: { mode: "drop", columns: [column], renames: {} } satisfies SelectConfig,
  });
}

export function filterByValue(column: string, value: string | null): void {
  const { store, node } = selected();
  if (!node) return;
  const cond: Condition =
    value === null ? newCondition(column, "is_null") : newCondition(column, "eq", value);
  if (node.type === "filter" && (node.config as FilterConfig).mode === "rules") {
    store.updateConfig(node.id, (c) => {
      const cfg = c as FilterConfig;
      return { ...cfg, rules: { ...cfg.rules, conditions: [...cfg.rules.conditions, cond] } };
    });
    return;
  }
  const config: FilterConfig = {
    mode: "rules",
    rules: { kind: "group", op: "and", conditions: [cond] },
    formula: "",
  };
  store.addNode("filter", { after: node.id, config });
}

export function sortBy(column: string, direction: "asc" | "desc"): void {
  const { store, node } = selected();
  if (!node) return;
  const key = newSortKey(column, direction);
  if (node.type === "sort") {
    store.updateConfig(node.id, (c) => {
      const cfg = c as SortConfig;
      return { ...cfg, keys: [key, ...cfg.keys.filter((k) => k.column !== column)] };
    });
    return;
  }
  store.addNode("sort", { after: node.id, config: { keys: [key] } satisfies SortConfig });
}

export function groupBy(column: string): void {
  const { store, node } = selected();
  if (!node) return;
  store.addNode("group_by", {
    after: node.id,
    config: { keys: [column], aggs: [newAgg(null, "count")], measures: [] } satisfies GroupByConfig,
  });
}

export function newColumnFrom(column: string): void {
  const { store, node } = selected();
  if (!node) return;
  const config: CalculatedConfig = {
    name: `${column}_novo`,
    mode: "new",
    formula: `[${column.replace(/]/g, "]]")}]`,
  };
  store.addNode("calculated", { after: node.id, config });
}
