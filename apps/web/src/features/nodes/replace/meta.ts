import { Replace } from "lucide-react";

import type { ReplaceConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<ReplaceConfig> = {
  type: "replace",
  label: "Substituir valores",
  description: "Tabela de/para, trecho de texto ou expressão regular.",
  category: "columns",
  icon: Replace,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["de para", "trocar", "substituir", "regex", "corrigir"],
  next: ["group_by", "filter"],
  defaultConfig: () => ({ column: "", mode: "exact", rules: [], case_sensitive: true }),
  summary,
};
