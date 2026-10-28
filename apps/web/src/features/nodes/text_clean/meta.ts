import { Eraser } from "lucide-react";

import type { TextCleanConfig } from "@/api/types";

import type { NodeMeta } from "../types";
import { summary } from "./summary";

export const meta: NodeMeta<TextCleanConfig> = {
  type: "text_clean",
  label: "Limpar texto",
  description: "Aparar espaços, maiúsculas/minúsculas, remover acentos.",
  category: "columns",
  icon: Eraser,
  inputs: ["in"],
  hasOutput: true,
  keywords: ["trim", "espaços", "acentos", "maiúscula", "minúscula", "arrumar"],
  next: ["replace", "group_by", "join"],
  defaultConfig: () => ({
    columns: [],
    trim: true,
    collapse_spaces: true,
    case: "none",
    remove_accents: false,
    empty_as_null: false,
  }),
  summary,
};
