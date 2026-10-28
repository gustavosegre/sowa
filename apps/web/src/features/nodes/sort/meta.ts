import { ArrowDownUp } from "lucide-react";

import type { SortConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<SortConfig> = {
  type: "sort",
  label: "Ordenar",
  description: "Ordena as linhas por uma ou mais colunas.",
  category: "rows",
  icon: ArrowDownUp,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["ordem", "classificar", "ordenar"],
  next: ["output", "filter"],
  defaultConfig: () => ({ keys: [] }),
  summary,
};
