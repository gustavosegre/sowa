import { Sigma } from "lucide-react";

import type { CalculatedConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<CalculatedConfig> = {
  type: "calculated",
  label: "Coluna calculada",
  description: "Cria ou substitui uma coluna usando uma fórmula.",
  category: "columns",
  icon: Sigma,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["fórmula", "calcular", "nova coluna", "expressão"],
  next: ["group_by", "filter", "calculated", "output"],
  defaultConfig: () => ({ name: "nova_coluna", mode: "new", formula: "" }),
  summary,
};
