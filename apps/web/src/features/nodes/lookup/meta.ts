import { SearchCheck } from "lucide-react";

import type { LookupConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<LookupConfig> = {
  type: "lookup",
  label: "Procurar (PROCV)",
  description: "Traz colunas de outra tabela pela chave, sem multiplicar linhas.",
  category: "combine",
  icon: SearchCheck,
  inputs: ["main", "lookup"],
  hasOutput: true,
  keywords: ["procv", "vlookup", "procx", "buscar", "consultar"],
  next: ["calculated", "group_by"],
  defaultConfig: () => ({ keys: [], columns: [], prefix: "", on_multiple: "first" }),
  summary,
};
