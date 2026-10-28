import { Group } from "lucide-react";

import type { GroupByConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<GroupByConfig> = {
  type: "group_by",
  label: "Agrupar",
  description: "Agrupa linhas por chaves e calcula agregações e medidas.",
  category: "aggregate",
  icon: Group,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["agrupar", "somar", "total", "agregação", "resumo"],
  next: ["sort", "filter", "output"],
  defaultConfig: () => ({ keys: [], aggs: [], measures: [] }),
  summary,
};
