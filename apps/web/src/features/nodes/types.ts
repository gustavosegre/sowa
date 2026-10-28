import type { LucideIcon } from "lucide-react";

export type Category =
  "input" | "columns" | "rows" | "aggregate" | "combine" | "output" | "advanced" | "organize";

export interface NodeMeta<C = Record<string, unknown>> {
  type: string;
  label: string;
  description: string;
  category: Category;
  icon: LucideIcon;
  /** Named input handles (`in`, or `left`/`right`…). Empty for sources and annotations. */
  inputs: string[];
  hasOutput: boolean;
  annotation?: boolean;
  /** Not offered in the library/menus (created another way, e.g. sub-flows from templates). */
  hidden?: boolean;
  /** Input handles that depend on the config (sub-flows); defaults to `inputs`. */
  inputsFor?: (config: C) => string[];
  /** Name of an input handle for this config (e.g. the sub-flow input name). */
  inputLabel?: (config: C, handle: string) => string | null;
  keywords?: string[];
  /** Most likely next steps, for the "+" menu on the node output. */
  next?: string[];
  defaultConfig: () => C;
  summary: (config: C) => string;
}

export const CATEGORY_ORDER: Category[] = [
  "input",
  "columns",
  "rows",
  "aggregate",
  "combine",
  "output",
  "advanced",
  "organize",
];

export const CATEGORY_COLOR: Record<Category, string> = {
  input: "var(--cat-input)",
  columns: "var(--cat-columns)",
  rows: "var(--cat-rows)",
  aggregate: "var(--cat-aggregate)",
  combine: "var(--cat-combine)",
  output: "var(--cat-output)",
  advanced: "var(--cat-advanced)",
  organize: "var(--cat-organize)",
};
