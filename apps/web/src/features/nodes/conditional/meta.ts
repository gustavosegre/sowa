import { GitBranch } from "lucide-react";

import type { ConditionalConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<ConditionalConfig> = {
  type: "conditional",
  label: "Coluna condicional",
  description: "Regras SE/SENÃO montadas visualmente, sem fórmula.",
  category: "columns",
  icon: GitBranch,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["se", "senão", "condição", "case when", "regra"],
  next: ["group_by", "filter"],
  defaultConfig: () => ({
    name: "categoria",
    mode: "new",
    rules: [],
    otherwise: { kind: "value", value: null, column: null },
    value_type: null,
  }),
  summary,
};
