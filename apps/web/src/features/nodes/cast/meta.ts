import { Shapes } from "lucide-react";

import type { CastConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<CastConfig> = {
  type: "cast",
  label: "Alterar tipo",
  description: "Converte tipos (datas, decimais BR, booleanos) com relatório de falhas.",
  category: "columns",
  icon: Shapes,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["tipo", "converter", "data", "número", "decimal"],
  next: ["calculated", "filter", "group_by"],
  defaultConfig: () => ({ casts: [] }),
  summary,
};
