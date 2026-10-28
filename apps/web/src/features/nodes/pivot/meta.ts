import { Table2 } from "lucide-react";

import type { PivotConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<PivotConfig> = {
  type: "pivot",
  label: "Tabela dinâmica",
  description: "Filtros, Linhas, Colunas e Valores, como no Excel.",
  category: "aggregate",
  icon: Table2,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["dinâmica", "pivot", "cruzamento", "matriz", "resumo"],
  next: ["output", "sort"],
  defaultConfig: () => ({
    rows: [],
    columns: null,
    values: [],
    filters: [],
    column_values: [],
    name_template: "{valor} · {medida}",
    totals: false,
  }),
  summary,
};
